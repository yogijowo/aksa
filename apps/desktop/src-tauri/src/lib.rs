pub mod sidecar;

use sidecar::{
    get_engine_connection_info, get_engine_lifecycle_state, sync_engine_port,
    update_engine_lifecycle_state, LifecycleState, SidecarState,
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

            match app.shell().sidecar("aksa-engine") {
                Ok(cmd) => {
                    let cmd = cmd
                        .args(["--host", &info.host, "--port", "0", "--production"])
                        .env("AKSA_AUTH_TOKEN", &info.auth_token)
                        .env("PYTHONUNBUFFERED", "1");

                    match cmd.spawn() {
                        Ok((mut rx, child)) => {
                            let child_pid = child.pid();
                            if let Ok(mut lock) = state.child_process.lock() {
                                *lock = Some(child);
                            }
                            // Keep in Starting state until health check & HMAC identity are verified
                            state.set_state(LifecycleState::Starting);
                            eprintln!("[AKSA Tauri] Sidecar spawned (PID: {}), awaiting port sync & HMAC identity verification", child_pid);

                            let app_handle = app.handle().clone();
                            tauri::async_runtime::spawn(async move {
                                use tauri_plugin_shell::process::CommandEvent;
                                while let Some(event) = rx.recv().await {
                                    match event {
                                        CommandEvent::Stderr(line_bytes) | CommandEvent::Stdout(line_bytes) => {
                                            let text = String::from_utf8_lossy(&line_bytes);
                                            if text.contains("[AKSA_ENGINE_READY:") {
                                                let mut ready_port: Option<u16> = None;
                                                let mut ready_pid: Option<u32> = None;

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

                                                if let (Some(p), Some(reported_pid)) = (ready_port, ready_pid) {
                                                    let s = app_handle.state::<SidecarState>();
                                                    if reported_pid != child_pid {
                                                        eprintln!(
                                                            "[AKSA Tauri Security Alert] PID mismatch in readiness marker: reported {} != child {}. Rejecting engine handshake!",
                                                            reported_pid, child_pid
                                                        );
                                                        s.set_state(LifecycleState::Failed);
                                                        s.shutdown();
                                                    } else {
                                                        s.sync_port(p);
                                                        let auth_token = s.info.lock().map(|i| i.auth_token.clone()).unwrap_or_default();
                                                        match crate::sidecar::verify_engine_health(p, &auth_token, 3000) {
                                                            Ok(true) => {
                                                                s.set_state(LifecycleState::Ready);
                                                                eprintln!(
                                                                    "[AKSA Tauri] Sidecar port {} and PID {} verified & health check passed. Lifecycle: Ready",
                                                                    p, child_pid
                                                                );
                                                            }
                                                            Ok(false) => {
                                                                eprintln!(
                                                                    "[AKSA Tauri Security Alert] Health check returned false for sidecar on port {}",
                                                                    p
                                                                );
                                                                s.set_state(LifecycleState::Failed);
                                                                s.shutdown();
                                                            }
                                                            Err(e) => {
                                                                eprintln!(
                                                                    "[AKSA Tauri Security Alert] Health check failed for sidecar on port {}: {}",
                                                                    p, e
                                                                );
                                                                s.set_state(LifecycleState::Failed);
                                                                s.shutdown();
                                                            }
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

