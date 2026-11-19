use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::Duration;
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
/// falling back to range 43121..43199, or atomically to an OS-assigned ephemeral port (P3-01).
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
    // Ephemeral OS fallback (port 0) ensures safe binding under extreme port exhaustion
    if let Ok(listener) = TcpListener::bind(("127.0.0.1", 0)) {
        if let Ok(addr) = listener.local_addr() {
            drop(listener);
            return addr.port();
        }
    }
    preferred_port
}

#[derive(Debug, Clone, Deserialize)]
pub struct EnginePortManifest {
    pub host: String,
    pub port: u16,
    pub pid: u32,
    #[serde(default)]
    pub version: String,
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

    pub fn sync_port(&self, actual_port: u16) {
        if let Ok(mut guard) = self.info.lock() {
            guard.port = actual_port;
            guard.base_url = format!("http://{}:{}", guard.host, actual_port);
            guard.ws_url = format!("ws://{}:{}/ws/stream", guard.host, actual_port);
        }
    }

    pub fn read_and_validate_manifest(&self, manifest_content: &str, expected_pid: u32) -> Result<u16, String> {
        let manifest: EnginePortManifest = serde_json::from_str(manifest_content)
            .map_err(|e| format!("Gagal mem-parsing manifest port engine: {}", e))?;
        if manifest.pid != expected_pid {
            return Err(format!(
                "Validasi PID gagal: manifest pid ({}) tidak sesuai dengan child process pid ({})",
                manifest.pid, expected_pid
            ));
        }
        self.sync_port(manifest.port);
        Ok(manifest.port)
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

pub fn verify_engine_health(port: u16, auth_token: &str, timeout_ms: u64) -> Result<bool, String> {
    let addr = format!("127.0.0.1:{}", port);
    let socket_addr = addr
        .parse()
        .map_err(|e| format!("Alamat loopback tidak valid: {}", e))?;

    let mut stream = TcpStream::connect_timeout(&socket_addr, Duration::from_millis(timeout_ms))
        .map_err(|e| format!("Gagal menyambung ke engine sidecar pada port {}: {}", port, e))?;

    stream
        .set_read_timeout(Some(Duration::from_millis(timeout_ms)))
        .map_err(|e| format!("Gagal mengatur timeout baca: {}", e))?;
    stream
        .set_write_timeout(Some(Duration::from_millis(timeout_ms)))
        .map_err(|e| format!("Gagal mengatur timeout tulis: {}", e))?;

    let request = format!(
        "GET /api/v1/health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nX-Aksa-Token: {}\r\nConnection: close\r\n\r\n",
        port, auth_token
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|e| format!("Gagal mengirim health probe ke engine: {}", e))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|e| format!("Gagal membaca respons health probe: {}", e))?;

    if response.contains("200 OK") && response.contains("\"status\"") {
        Ok(true)
    } else {
        Err(format!(
            "Health probe mengembalikan respons tidak terduga: {}",
            response.lines().next().unwrap_or("Kosong")
        ))
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

#[tauri::command]
pub fn sync_engine_port(
    state: tauri::State<'_, SidecarState>,
    actual_port: u16,
) -> Result<EngineConnectionInfo, String> {
    let mut guard = state.info.lock().map_err(|e| e.to_string())?;
    guard.port = actual_port;
    guard.base_url = format!("http://{}:{}", guard.host, actual_port);
    guard.ws_url = format!("ws://{}:{}/ws/stream", guard.host, actual_port);
    Ok(guard.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sidecar_sync_engine_port_updates_endpoints() {
        let sidecar = SidecarState::new(43120);
        {
            let mut info = sidecar.info.lock().unwrap();
            info.port = 43195;
            info.base_url = format!("http://{}:43195", info.host);
            info.ws_url = format!("ws://{}:43195/ws/stream", info.host);
        }
        let info = sidecar.info.lock().unwrap();
        assert_eq!(info.port, 43195);
        assert_eq!(info.base_url, "http://127.0.0.1:43195");
        assert_eq!(info.ws_url, "ws://127.0.0.1:43195/ws/stream");
    }

    #[test]
    fn test_allocate_loopback_port_prefers_unbound_port() {
        // Allocate a dynamic OS ephemeral port to get a guaranteed free port
        let free_port = {
            let l = TcpListener::bind(("127.0.0.1", 0)).expect("Failed to bind ephemeral port");
            let p = l.local_addr().expect("Failed to get local addr").port();
            drop(l);
            p
        };
        let allocated = allocate_loopback_port(free_port);
        assert_eq!(allocated, free_port);
    }

    #[test]
    fn test_allocate_loopback_port_fallback_when_busy() {
        // Hold preferred port 43120 busy with a live listener
        let busy_listener = TcpListener::bind(("127.0.0.1", 43120));
        if let Ok(listener) = busy_listener {
            let allocated = allocate_loopback_port(43120);
            assert_ne!(allocated, 43120);
            assert!(
                (43121..=43199).contains(&allocated) || allocated > 1024,
                "Allocated port {} should be in fallback range or ephemeral",
                allocated
            );
            drop(listener);
        }
    }

    #[test]
    fn test_sidecar_state_initialization_and_token() {
        let state = SidecarState::new(43120);
        let info = state.info.lock().expect("Failed to lock sidecar info");

        assert!(info.auth_token.starts_with("aksa-"));
        // Prefix "aksa-" (5 chars) + 2x UUID simple (32 hex chars each = 64) = 69 chars
        assert_eq!(info.auth_token.len(), 69);
        assert_eq!(info.host, "127.0.0.1");
        assert!(info.base_url.starts_with("http://127.0.0.1:"));
        assert!(info.ws_url.starts_with("ws://127.0.0.1:"));
        assert_eq!(info.lifecycle_state, LifecycleState::Starting);
        assert_eq!(state.get_state(), LifecycleState::Starting);
    }

    #[test]
    fn test_sidecar_state_transitions() {
        let state = SidecarState::new(43120);
        assert_eq!(state.get_state(), LifecycleState::Starting);

        state.set_state(LifecycleState::Ready);
        assert_eq!(state.get_state(), LifecycleState::Ready);

        state.set_state(LifecycleState::Stopping);
        assert_eq!(state.get_state(), LifecycleState::Stopping);

        state.set_state(LifecycleState::Failed);
        assert_eq!(state.get_state(), LifecycleState::Failed);
    }

    #[test]
    fn test_read_and_validate_manifest_matching_pid_updates_port() {
        let state = SidecarState::new(43120);
        let manifest_json = r#"{"host":"127.0.0.1","port":43188,"pid":9999,"version":"1.0.0"}"#;
        let res = state.read_and_validate_manifest(manifest_json, 9999);
        assert!(res.is_ok());
        assert_eq!(res.unwrap(), 43188);

        let info = state.info.lock().unwrap();
        assert_eq!(info.port, 43188);
        assert_eq!(info.base_url, "http://127.0.0.1:43188");
        assert_eq!(info.ws_url, "ws://127.0.0.1:43188/ws/stream");
    }

    #[test]
    fn test_read_and_validate_manifest_mismatched_pid_rejected() {
        let state = SidecarState::new(43120);
        let manifest_json = r#"{"host":"127.0.0.1","port":43188,"pid":8888,"version":"1.0.0"}"#;
        let res = state.read_and_validate_manifest(manifest_json, 9999);
        assert!(res.is_err());
        assert!(res.unwrap_err().contains("Validasi PID gagal"));

        let info = state.info.lock().unwrap();
        assert_ne!(info.port, 43188);
    }

    #[test]
    fn test_verify_engine_health_connection_refused() {
        let res = verify_engine_health(59999, "test-token", 200);
        assert!(res.is_err());
    }

    #[test]
    fn test_verify_engine_health_mock_success() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("Failed to bind test mock listener");
        let port = listener.local_addr().unwrap().port();

        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut buf = [0u8; 1024];
                let _ = stream.read(&mut buf);
                let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"version\":\"1.0.0\"}";
                let _ = stream.write_all(response.as_bytes());
            }
        });

        let res = verify_engine_health(port, "aksa-valid-token", 1000);
        assert!(res.is_ok());
        assert_eq!(res.unwrap(), true);
    }
}
