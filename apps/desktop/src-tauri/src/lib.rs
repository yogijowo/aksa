pub mod sidecar;

use sidecar::{get_engine_connection_info, SidecarState};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_state = SidecarState::new(43120);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(sidecar_state)
        .invoke_handler(tauri::generate_handler![get_engine_connection_info])
        .run(tauri::generate_context!())
        .expect("Gagal menjalankan aplikasi desktop AKSA");
}

