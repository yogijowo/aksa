pub mod sidecar;

use sidecar::{get_engine_connection_info, SidecarState};
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
        .invoke_handler(tauri::generate_handler![get_engine_connection_info])
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
                        Ok((_rx, child)) => {
                            if let Ok(mut lock) = state.child_process.lock() {
                                *lock = Some(child);
                            }
                            eprintln!("[AKSA Tauri] Sidecar berhasil dijalankan pada port {}", info.port);
                        }
                        Err(e) => {
                            eprintln!("[AKSA Tauri] Peringatan: Sidecar tidak dapat di-spawn (kemungkinan dev runner aktif): {}", e);
                        }
                    }
                }
                Err(e) => {
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

