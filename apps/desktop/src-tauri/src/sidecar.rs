use serde::{Deserialize, Serialize};
use std::net::TcpListener;
use std::sync::Mutex;
use tauri_plugin_shell::process::CommandChild;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LifecycleState {
    Starting,
    Ready,
    Failed,
    Stopping,
}

#[derive(Debug, Clone, Serialize)]
pub struct EngineConnectionInfo {
    pub host: String,
    pub port: u16,
    pub auth_token: String,
    pub base_url: String,
    pub ws_url: String,
    pub lifecycle_state: LifecycleState,
}

pub struct SidecarState {
    pub info: Mutex<EngineConnectionInfo>,
    pub child_process: Mutex<Option<CommandChild>>,
    pub lifecycle_state: Mutex<LifecycleState>,
}

/// Allocate an available loopback-only port, preferring `preferred_port` if free,
/// otherwise falling back to an OS-assigned loopback port in range 43121..43199.
pub fn allocate_loopback_port(preferred_port: u16) -> u16 {
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", preferred_port)) {
        drop(listener);
        return preferred_port;
    }
    for port in 43121..43199 {
        if let Ok(listener) = TcpListener::bind(("127.0.0.1", port)) {
            drop(listener);
            return port;
        }
    }
    preferred_port
}

impl SidecarState {
    pub fn new(preferred_port: u16) -> Self {
        let port = allocate_loopback_port(preferred_port);
        // Generate 256-bit (64 hex chars) per-launch CSPRNG handshake token
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
            lifecycle_state: LifecycleState::Starting,
        };
        Self {
            info: Mutex::new(info),
            child_process: Mutex::new(None),
            lifecycle_state: Mutex::new(LifecycleState::Starting),
        }
    }

    pub fn set_state(&self, state: LifecycleState) {
        if let Ok(mut lock) = self.lifecycle_state.lock() {
            *lock = state;
        }
        if let Ok(mut info_lock) = self.info.lock() {
            info_lock.lifecycle_state = state;
        }
    }

    pub fn get_state(&self) -> LifecycleState {
        self.lifecycle_state.lock().map(|g| *g).unwrap_or(LifecycleState::Failed)
    }

    pub fn shutdown(&self) {
        self.set_state(LifecycleState::Stopping);
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

#[tauri::command]
pub fn get_engine_lifecycle_state(
    state: tauri::State<'_, SidecarState>,
) -> Result<LifecycleState, String> {
    Ok(state.get_state())
}

#[tauri::command]
pub fn update_engine_lifecycle_state(
    state: tauri::State<'_, SidecarState>,
    new_state: LifecycleState,
) -> Result<(), String> {
    state.set_state(new_state);
    Ok(())
}
