pub mod sidecar;

use sidecar::{
    get_engine_connection_info, get_engine_lifecycle_state, prepare_runtime_manifest_slot,
    sync_engine_port, update_engine_lifecycle_state, LifecycleState, SidecarState,
};
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_state = SidecarState::new(43120);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(sidecar_state)
        .invoke_handler(tauri::generate_handler![
            get_engine_connection_info,
            get_engine_lifecycle_state,
            update_engine_lifecycle_state,
            sync_engine_port
        ])
        .setup(|app| {
            let state = app.state::<SidecarState>();
            let info = state.info.lock().map_err(|e| e.to_string())?.clone();
            let launch_id = state.launch_id.clone();

            // Resolve AppData dir & prepare unique per-launch runtime manifest slot BEFORE spawn (fail-closed)
            let app_data = match app.path().app_data_dir() {
                Ok(dir) => dir,
                Err(e) => {
                    state.set_state(LifecycleState::Failed);
                    eprintln!("[AKSA Tauri Security Alert] Gagal menyelesaikan app_data_dir (spawn dibatalkan): {}", e);
                    return Ok(());
                }
            };
            let runtime_dir = app_data.join("runtime");
            let manifest_path = match prepare_runtime_manifest_slot(&runtime_dir, &launch_id) {
                Ok(p) => p,
                Err(e) => {
                    state.set_state(LifecycleState::Failed);
                    eprintln!("[AKSA Tauri Security Alert] Gagal menyiapkan slot manifest runtime (spawn dibatalkan): {}", e);
                    return Ok(());
                }
            };
            state.set_manifest_path(manifest_path.clone());

            match app.shell().sidecar("aksa-engine") {
                Ok(cmd) => {
                    let cmd = cmd
                        .args(["--host", &info.host, "--port", "0", "--production"])
                        .env("AKSA_AUTH_TOKEN", &info.auth_token)
                        .env("AKSA_LAUNCH_ID", &launch_id)
                        .env("AKSA_APPDATA_DIR", app_data.to_string_lossy().as_ref())
                        .env("AKSA_MANIFEST_PATH", manifest_path.to_string_lossy().as_ref())
                        .env("PYTHONUNBUFFERED", "1");

                    match cmd.spawn() {
                        Ok((mut rx, child)) => {
                            let child_pid = child.pid();
                            if let Ok(mut lock) = state.child_process.lock() {
                                *lock = Some(child);
                            }
                            // Keep in Starting state until manifest + PID + launch_id + HMAC are verified
                            state.set_state(LifecycleState::Starting);
                            eprintln!(
                                "[AKSA Tauri] Sidecar spawned (PID: {}, launch: {}), awaiting mandatory manifest & HMAC handshake",
                                child_pid, launch_id
                            );

                            let app_handle = app.handle().clone();
                            let expected_manifest_path = manifest_path.clone();
                            tauri::async_runtime::spawn(async move {
                                use tauri_plugin_shell::process::CommandEvent;
                                while let Some(event) = rx.recv().await {
                                    match event {
                                        CommandEvent::Stderr(line_bytes) | CommandEvent::Stdout(line_bytes) => {
                                            let text = String::from_utf8_lossy(&line_bytes);
                                            if text.contains("[AKSA_ENGINE_READY:") {
                                                let mut ready_port: Option<u16> = None;
                                                let mut ready_pid: Option<u32> = None;
                                                let mut ready_launch_id: Option<String> = None;

                                                if let Some(port_start) = text.find("port=") {
                                                    let sub = &text[port_start + 5..];
                                                    let port_str = sub.split(|c| c == ':' || c == ']').next().unwrap_or("");
                                                    ready_port = port_str.parse::<u16>().ok();
                                                }
                                                if let Some(pid_start) = text.find("pid=") {
                                                    let sub = &text[pid_start + 4..];
                                                    let pid_str = sub.split(|c| c == ':' || c == ']').next().unwrap_or("");
                                                    ready_pid = pid_str.parse::<u32>().ok();
                                                }
                                                if let Some(lid_start) = text.find("launch_id=") {
                                                    let sub = &text[lid_start + 10..];
                                                    let lid_str = sub.split(|c| c == ':' || c == ']').next().unwrap_or("").trim();
                                                    if !lid_str.is_empty() {
                                                        ready_launch_id = Some(lid_str.to_string());
                                                    }
                                                }

                                                if let (Some(p), Some(reported_pid)) = (ready_port, ready_pid) {
                                                    let s = app_handle.state::<SidecarState>();
                                                    let auth_token = s.info.lock().map(|i| i.auth_token.clone()).unwrap_or_default();

                                                    // Mandatory per-launch manifest lookup (brief retry if filesystem rename lagged slightly)
                                                    let mut manifest_content: Option<String> = None;
                                                    for _ in 0..10 {
                                                        if let Ok(content) = std::fs::read_to_string(&expected_manifest_path) {
                                                            manifest_content = Some(content);
                                                            break;
                                                        }
                                                        std::thread::sleep(std::time::Duration::from_millis(25));
                                                    }

                                                    match s.validate_and_sync_handshake(
                                                        p,
                                                        reported_pid,
                                                        child_pid,
                                                        ready_launch_id.as_deref(),
                                                        manifest_content.as_deref(),
                                                        &auth_token,
                                                    ) {
                                                        Ok(synced_port) => {
                                                            eprintln!(
                                                                "[AKSA Tauri] Sidecar port {} and PID {} verified (mandatory manifest + launch_id + HMAC + health passed). Lifecycle: Ready",
                                                                synced_port, child_pid
                                                            );
                                                        }
                                                        Err(e) => {
                                                            eprintln!(
                                                                "[AKSA Tauri Security Alert] Sidecar handshake failed for port {} (PID {}): {}",
                                                                p, child_pid, e
                                                            );
                                                            s.set_state(LifecycleState::Failed);
                                                            s.shutdown();
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        CommandEvent::Terminated(payload) => {
                                            eprintln!("[AKSA Tauri] Sidecar terminated: {:?}", payload);
                                            let s = app_handle.state::<SidecarState>();
                                            s.set_state(LifecycleState::Failed);
                                            break;
                                        }
                                        _ => {}
                                    }
                                }
                            });
                        }
                        Err(e) => {
                            state.set_state(LifecycleState::Failed);
                            eprintln!("[AKSA Tauri] Peringatan: Sidecar tidak dapat di-spawn (kemungkinan dev runner aktif): {}", e);
                        }
                    }
                }
                Err(e) => {
                    state.set_state(LifecycleState::Failed);
                    eprintln!("[AKSA Tauri] Info: Sidecar aksa-engine command: {}", e);
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Gagal membangun aplikasi desktop AKSA")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app_handle.state::<SidecarState>();
                state.shutdown();
            }
        });
}

