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
                        .args(["--host", &info.host, "--port", &info.port.to_string(), "--production"])
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
                                                if let Some(port_start) = text.find("port=") {
                                                    let sub = &text[port_start + 5..];
                                                    let parts: Vec<&str> = sub.split(':').collect();
                                                    if let Some(port_str) = parts.first() {
                                                        if let Ok(p) = port_str.trim_end_matches(']').parse::<u16>() {
                                                            let s = app_handle.state::<SidecarState>();
                                                            s.sync_port(p);
                                                            eprintln!("[AKSA Tauri] Sidecar port synchronized from runtime readiness event: {}", p);
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

