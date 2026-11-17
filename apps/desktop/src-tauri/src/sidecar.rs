use serde::Serialize;
use std::sync::Mutex;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize)]
pub struct EngineConnectionInfo {
    pub host: String,
    pub port: u16,
    pub auth_token: String,
    pub base_url: String,
    pub ws_url: String,
}

pub struct SidecarState {
    pub info: Mutex<EngineConnectionInfo>,
}

impl SidecarState {
    pub fn new(port: u16) -> Self {
        let token = format!("aksa-{}", Uuid::new_v4());
        let host = "127.0.0.1".to_string();
        let info = EngineConnectionInfo {
            base_url: format!("http://{}:{}", host, port),
            ws_url: format!("ws://{}:{}/ws/stream", host, port),
            host,
            port,
            auth_token: token,
        };
        Self {
            info: Mutex::new(info),
        }
    }
}

#[tauri::command]
pub fn get_engine_connection_info(
    state: tauri::State<'_, SidecarState>,
) -> Result<EngineConnectionInfo, String> {
    let guard = state.info.lock().map_err(|e| e.to_string())?;
    Ok(guard.clone())
}

