use serde::Serialize;
use std::net::TcpListener;
use std::sync::Mutex;
use tauri_plugin_shell::process::CommandChild;
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
    pub child_process: Mutex<Option<CommandChild>>,
}

/// Allocate an available loopback-only port, preferring `preferred_port` if free,
/// otherwise falling back to an OS-assigned ephemeral port on 127.0.0.1.
pub fn allocate_loopback_port(preferred_port: u16) -> u16 {
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", preferred_port)) {
        if let Ok(addr) = listener.local_addr() {
            return addr.port();
        }
    }
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", 0)) {
        if let Ok(addr) = listener.local_addr() {
            return addr.port();
        }
    }
    preferred_port
}

impl SidecarState {
    pub fn new(preferred_port: u16) -> Self {
        let port = allocate_loopback_port(preferred_port);
        // Generate 256-bit (64 hex chars) per-launch handshake token
        let token = format!(
            "aksa-{}{}",
            Uuid::new_v4().as_simple(),
            Uuid::new_v4().as_simple()
        );
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
            child_process: Mutex::new(None),
        }
    }

    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.child_process.lock() {
            if let Some(child) = guard.take() {
                let _ = child.kill();
            }
        }
    }
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[tauri::command]
pub fn get_engine_connection_info(
    state: tauri::State<'_, SidecarState>,
) -> Result<EngineConnectionInfo, String> {
    let guard = state.info.lock().map_err(|e| e.to_string())?;
    Ok(guard.clone())
}
