use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::Mutex;
use std::time::Duration;
use tauri_plugin_shell::process::CommandChild;
use uuid::Uuid;

pub const EXPECTED_ENGINE_VERSION: &str = "1.0.0";

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
    pub launch_id: String,
    pub expected_version: String,
    pub handshake_verified: Mutex<bool>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EnginePortManifest {
    pub host: String,
    pub port: u16,
    pub pid: u32,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub launch_id: String,
}

impl SidecarState {
    pub fn new(_unused_preferred_port: u16) -> Self {
        // AKSA-SEC-004-R5: No bind-then-drop pre-allocation. Engine binds port 0 itself and proves
        // its bound port via atomic manifest + PID + launch_id + nonce HMAC before becoming Ready.
        let token = format!(
            "aksa-{}{}",
            Uuid::new_v4().as_simple(),
            Uuid::new_v4().as_simple()
        );
        let launch_id = format!("launch-{}", Uuid::new_v4().as_simple());
        let host = "127.0.0.1".to_string();
        let info = EngineConnectionInfo {
            base_url: String::new(),
            ws_url: String::new(),
            host,
            port: 0,
            auth_token: token,
            lifecycle_state: LifecycleState::Starting,
        };
        Self {
            info: Mutex::new(info),
            child_process: Mutex::new(None),
            lifecycle_state: Mutex::new(LifecycleState::Starting),
            launch_id,
            expected_version: EXPECTED_ENGINE_VERSION.to_string(),
            handshake_verified: Mutex::new(false),
        }
    }

    pub fn sync_port(&self, actual_port: u16) {
        if let Ok(mut guard) = self.info.lock() {
            guard.port = actual_port;
            guard.base_url = format!("http://{}:{}", guard.host, actual_port);
            guard.ws_url = format!("ws://{}:{}/ws/stream", guard.host, actual_port);
        }
    }

    pub fn read_and_validate_manifest_strict(
        &self,
        manifest_content: &str,
        expected_pid: u32,
        expected_version: &str,
        expected_launch_id: &str,
    ) -> Result<u16, String> {
        let manifest: EnginePortManifest = serde_json::from_str(manifest_content)
            .map_err(|e| format!("Gagal mem-parsing manifest port engine: {}", e))?;

        if manifest.host != "127.0.0.1" {
            return Err(format!(
                "Validasi host gagal: manifest host ('{}') bukan loopback 127.0.0.1",
                manifest.host
            ));
        }
        if manifest.port == 0 {
            return Err("Validasi port gagal: port manifest tidak boleh 0".to_string());
        }
        if manifest.pid != expected_pid {
            return Err(format!(
                "Validasi PID gagal: manifest pid ({}) tidak sesuai dengan child process pid ({})",
                manifest.pid, expected_pid
            ));
        }
        if manifest.version.is_empty() || manifest.version != expected_version {
            return Err(format!(
                "Validasi versi gagal: manifest version ('{}') tidak sesuai dengan expected ('{}')",
                manifest.version, expected_version
            ));
        }
        if expected_launch_id.is_empty() || manifest.launch_id != expected_launch_id {
            return Err(format!(
                "Validasi launch_id gagal: manifest stale atau bukan milik proses ini ('{}' != '{}')",
                manifest.launch_id, expected_launch_id
            ));
        }

        Ok(manifest.port)
    }

    pub fn read_and_validate_manifest(&self, manifest_content: &str, expected_pid: u32) -> Result<u16, String> {
        let manifest: EnginePortManifest = serde_json::from_str(manifest_content)
            .map_err(|e| format!("Gagal mem-parsing manifest port engine: {}", e))?;
        if manifest.host != "127.0.0.1" {
            return Err(format!(
                "Validasi host gagal: manifest host ('{}') bukan loopback 127.0.0.1",
                manifest.host
            ));
        }
        if manifest.port == 0 {
            return Err("Validasi port gagal: port manifest tidak boleh 0".to_string());
        }
        if manifest.pid != expected_pid {
            return Err(format!(
                "Validasi PID gagal: manifest pid ({}) tidak sesuai dengan child process pid ({})",
                manifest.pid, expected_pid
            ));
        }
        if manifest.version.is_empty() || manifest.version != self.expected_version {
            return Err(format!(
                "Validasi versi gagal: manifest version ('{}') tidak sesuai dengan '{}'",
                manifest.version, self.expected_version
            ));
        }
        self.sync_port(manifest.port);
        Ok(manifest.port)
    }

    /// Unified fail-closed startup handshake: validates marker PID, marker launch_id,
    /// mandatory runtime manifest (host, port, PID, version, launch_id), and nonce HMAC
    /// BEFORE transitioning lifecycle to Ready.
    pub fn validate_and_sync_handshake(
        &self,
        reported_port: u16,
        reported_pid: u32,
        child_pid: u32,
        reported_launch_id: Option<&str>,
        manifest_content: Option<&str>,
        auth_token: &str,
    ) -> Result<u16, String> {
        let result = (|| -> Result<u16, String> {
            if reported_port == 0 {
                return Err("Readiness marker melaporkan port 0 yang tidak valid".to_string());
            }
            if reported_pid != child_pid {
                return Err(format!(
                    "Validasi PID gagal: reported pid ({}) tidak sesuai dengan child process pid ({})",
                    reported_pid, child_pid
                ));
            }
            match reported_launch_id {
                Some(lid) if !lid.is_empty() && lid == self.launch_id => {}
                Some(lid) => {
                    return Err(format!(
                        "Validasi launch_id marker gagal: '{}' != '{}'",
                        lid, self.launch_id
                    ));
                }
                None => {
                    return Err("Readiness marker tidak menyertakan launch_id sesi".to_string());
                }
            }

            let content = manifest_content.ok_or_else(|| {
                "Manifest runtime engine_port.json tidak ditemukan (wajib ada sebelum READY, fail-closed)".to_string()
            })?;

            let manifest_port = self.read_and_validate_manifest_strict(
                content,
                child_pid,
                &self.expected_version,
                &self.launch_id,
            )?;

            if manifest_port != reported_port {
                return Err(format!(
                    "Validasi Port gagal: port manifest ({}) tidak sesuai dengan readiness marker ({})",
                    manifest_port, reported_port
                ));
            }

            verify_engine_health(reported_port, auth_token, 3000)?;
            Ok(reported_port)
        })();

        match result {
            Ok(port) => {
                if let Ok(mut verified) = self.handshake_verified.lock() {
                    *verified = true;
                }
                self.sync_port(port);
                self.set_state(LifecycleState::Ready);
                Ok(port)
            }
            Err(err) => {
                if let Ok(mut verified) = self.handshake_verified.lock() {
                    *verified = false;
                }
                self.set_state(LifecycleState::Failed);
                Err(err)
            }
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

/// Compute lowercase-hex HMAC-SHA256(token, nonce).
pub fn compute_nonce_hmac(auth_token: &str, nonce: &str) -> String {
    use hmac::{Hmac, Mac};
    use sha2::Sha256;
    let mut mac = Hmac::<Sha256>::new_from_slice(auth_token.as_bytes())
        .expect("HMAC accepts keys of any length");
    mac.update(nonce.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b.iter()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// Validate a raw HTTP health response: status 200, JSON body, engine marker and matching nonce HMAC.
pub fn verify_health_response(response: &str, auth_token: &str, nonce: &str) -> Result<bool, String> {
    let status_line = response.lines().next().unwrap_or("");
    if !status_line.contains(" 200") {
        return Err(format!("Health probe mengembalikan status tidak terduga: {}", status_line));
    }
    let body = response
        .split_once("\r\n\r\n")
        .map(|(_, b)| b)
        .ok_or_else(|| "Respons health tidak memiliki body".to_string())?;
    let json: serde_json::Value =
        serde_json::from_str(body.trim()).map_err(|e| format!("Body health bukan JSON valid: {}", e))?;
    if json.get("engine").and_then(|v| v.as_str()) != Some("aksa-engine") {
        return Err("Respons health bukan dari aksa-engine".to_string());
    }
    let reported = json
        .get("nonce_hmac")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Respons health tidak menyertakan nonce_hmac".to_string())?;
    let expected = compute_nonce_hmac(auth_token, nonce);
    if constant_time_eq(reported.as_bytes(), expected.as_bytes()) {
        Ok(true)
    } else {
        Err("Verifikasi HMAC identitas engine gagal (kemungkinan proses palsu pada port ini)".to_string())
    }
}

/// Loopback health probe with random nonce and HMAC challenge-response identity verification.
/// Security invariant: NEVER sends `X-AKSA-Auth-Token` before HMAC identity is proven.
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

    let nonce = Uuid::new_v4().as_simple().to_string();
    // NEVER send X-AKSA-Auth-Token before server proves knowledge of secret via HMAC!
    let request = format!(
        "GET /api/v1/health?nonce={} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        nonce, port
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|e| format!("Gagal mengirim health probe ke engine: {}", e))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|e| format!("Gagal membaca respons health probe: {}", e))?;

    verify_health_response(&response, auth_token, &nonce)
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

impl SidecarState {
    pub fn set_state_from_ipc(&self, new_state: LifecycleState) -> Result<(), String> {
        if new_state == LifecycleState::Ready {
            let verified = self.handshake_verified.lock().map(|v| *v).unwrap_or(false);
            if !verified {
                return Err("Ditolak: Status Ready hanya dapat ditetapkan setelah handshake manifest & HMAC sidecar berhasil.".to_string());
            }
        }
        self.set_state(new_state);
        Ok(())
    }
}

#[tauri::command]
pub fn update_engine_lifecycle_state(
    state: tauri::State<'_, SidecarState>,
    new_state: LifecycleState,
) -> Result<(), String> {
    state.set_state_from_ipc(new_state)
}

#[tauri::command]
pub fn sync_engine_port(
    state: tauri::State<'_, SidecarState>,
    _actual_port: u16,
) -> Result<EngineConnectionInfo, String> {
    let verified = state.handshake_verified.lock().map(|v| *v).unwrap_or(false);
    if !verified {
        return Err("Ditolak: Port sidecar tidak boleh disinkronkan secara manual sebelum manifest tervalidasi.".to_string());
    }
    let guard = state.info.lock().map_err(|e| e.to_string())?;
    Ok(guard.clone())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    #[test]
    fn test_sidecar_starts_unbound_with_zero_port_and_no_bind_race() {
        let state = SidecarState::new(43120);
        let info = state.info.lock().expect("Failed to lock sidecar info");

        assert!(info.auth_token.starts_with("aksa-"));
        assert_eq!(info.auth_token.len(), 69);
        assert!(state.launch_id.starts_with("launch-"));
        assert_eq!(info.host, "127.0.0.1");
        assert_eq!(info.port, 0);
        assert!(info.base_url.is_empty());
        assert!(info.ws_url.is_empty());
        assert_eq!(info.lifecycle_state, LifecycleState::Starting);
        assert_eq!(state.get_state(), LifecycleState::Starting);
    }

    #[test]
    fn test_read_and_validate_manifest_matching_pid_updates_port() {
        let state = SidecarState::new(0);
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
        let state = SidecarState::new(0);
        let manifest_json = r#"{"host":"127.0.0.1","port":43188,"pid":8888,"version":"1.0.0"}"#;
        let res = state.read_and_validate_manifest(manifest_json, 9999);
        assert!(res.unwrap_err().contains("Validasi PID gagal"));
    }

    #[test]
    fn test_manifest_non_loopback_host_rejected() {
        let state = SidecarState::new(0);
        let manifest = format!(
            r#"{{"host":"0.0.0.0","port":43188,"pid":9999,"version":"1.0.0","launch_id":"{}"}}"#,
            state.launch_id
        );
        let res = state.read_and_validate_manifest_strict(&manifest, 9999, "1.0.0", &state.launch_id);
        assert!(res.unwrap_err().contains("Validasi host gagal"));
    }

    #[test]
    fn test_manifest_wrong_version_rejected() {
        let state = SidecarState::new(0);
        let manifest = format!(
            r#"{{"host":"127.0.0.1","port":43188,"pid":9999,"version":"0.9.9","launch_id":"{}"}}"#,
            state.launch_id
        );
        let res = state.read_and_validate_manifest_strict(&manifest, 9999, "1.0.0", &state.launch_id);
        assert!(res.unwrap_err().contains("Validasi versi gagal"));
    }

    #[test]
    fn test_manifest_stale_launch_id_rejected() {
        let state = SidecarState::new(0);
        let manifest = r#"{"host":"127.0.0.1","port":43188,"pid":9999,"version":"1.0.0","launch_id":"launch-stale-old"}"#;
        let res = state.read_and_validate_manifest_strict(manifest, 9999, "1.0.0", &state.launch_id);
        assert!(res.unwrap_err().contains("Validasi launch_id gagal"));
    }

    fn spawn_fake_health_capture(
        body_fn: impl Fn(&str) -> String + Send + 'static,
    ) -> (u16, std::sync::mpsc::Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind fake health server");
        let port = listener.local_addr().unwrap().port();
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut buf = [0u8; 4096];
                let n = stream.read(&mut buf).unwrap_or(0);
                let req = String::from_utf8_lossy(&buf[..n]).to_string();
                let _ = tx.send(req.clone());
                let nonce = req
                    .split("nonce=")
                    .nth(1)
                    .and_then(|r| r.split(' ').next())
                    .unwrap_or("")
                    .to_string();
                let body = body_fn(&nonce);
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{}",
                    body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        });
        (port, rx)
    }

    #[test]
    fn test_verify_engine_health_never_leaks_auth_token_in_challenge() {
        let secret = "super-secret-aksa-token";
        let (port, rx) = spawn_fake_health_capture(move |nonce| {
            format!(
                "{{\"status\":\"ok\",\"engine\":\"aksa-engine\",\"nonce_hmac\":\"{}\"}}",
                compute_nonce_hmac(secret, nonce)
            )
        });
        assert_eq!(verify_engine_health(port, secret, 1000), Ok(true));
        let raw_req = rx.recv().expect("capture HTTP request");
        assert!(!raw_req.to_lowercase().contains("x-aksa-auth-token"));
        assert!(!raw_req.contains(secret));
    }

    #[test]
    fn test_verify_engine_health_fake_server_without_hmac_rejected() {
        let (port, _) = spawn_fake_health_capture(|_| "{\"status\":\"ok\",\"engine\":\"aksa-engine\"}".to_string());
        let res = verify_engine_health(port, "aksa-genuine-token", 1000);
        assert!(res.unwrap_err().contains("nonce_hmac"));
    }

    #[test]
    fn test_verify_engine_health_port_takeover_wrong_hmac_rejected() {
        let (port, _) = spawn_fake_health_capture(|nonce| {
            format!(
                "{{\"status\":\"ok\",\"engine\":\"aksa-engine\",\"nonce_hmac\":\"{}\"}}",
                compute_nonce_hmac("attacker-guess", nonce)
            )
        });
        let res = verify_engine_health(port, "aksa-genuine-token", 1000);
        assert!(res.unwrap_err().contains("HMAC"));
    }

    #[test]
    fn test_verify_engine_health_generic_200_server_rejected() {
        let (port, _) = spawn_fake_health_capture(|_| "{\"status\":\"ok\"}".to_string());
        assert!(verify_engine_health(port, "aksa-genuine-token", 1000).is_err());
    }

    #[test]
    fn test_validate_and_sync_handshake_missing_manifest_fails_closed() {
        let token = "aksa-sync-token";
        let state = SidecarState::new(0);
        let (port, _) = spawn_fake_health_capture({
            let t = token.to_string();
            move |nonce| {
                format!(
                    "{{\"status\":\"ok\",\"engine\":\"aksa-engine\",\"nonce_hmac\":\"{}\"}}",
                    compute_nonce_hmac(&t, nonce)
                )
            }
        });
        let lid = state.launch_id.clone();
        let res = state.validate_and_sync_handshake(port, 7777, 7777, Some(&lid), None, token);
        assert!(res.unwrap_err().contains("tidak ditemukan"));
        assert_eq!(state.get_state(), LifecycleState::Failed);
    }

    #[test]
    fn test_validate_and_sync_handshake_corrupt_manifest_fails_closed() {
        let state = SidecarState::new(0);
        let lid = state.launch_id.clone();
        let res = state.validate_and_sync_handshake(43120, 7777, 7777, Some(&lid), Some("{corrupt"), "tok");
        assert!(res.unwrap_err().contains("Gagal mem-parsing"));
        assert_eq!(state.get_state(), LifecycleState::Failed);
    }

    #[test]
    fn test_validate_and_sync_handshake_pid_and_port_mismatch_fail() {
        let state = SidecarState::new(0);
        let lid = state.launch_id.clone();
        let res_pid = state.validate_and_sync_handshake(43120, 1111, 2222, Some(&lid), None, "token");
        assert!(res_pid.unwrap_err().contains("PID gagal"));

        let manifest = format!(
            r#"{{"host":"127.0.0.1","port":43188,"pid":9999,"version":"1.0.0","launch_id":"{}"}}"#,
            lid
        );
        let res_port = state.validate_and_sync_handshake(43120, 9999, 9999, Some(&lid), Some(&manifest), "token");
        assert!(res_port.unwrap_err().contains("Port gagal"));
    }

    #[test]
    fn test_validate_and_sync_handshake_genuine_manifest_and_hmac_passes() {
        let token = "aksa-sync-token";
        let state = SidecarState::new(0);
        let (port, _) = spawn_fake_health_capture({
            let t = token.to_string();
            move |nonce| {
                format!(
                    "{{\"status\":\"ok\",\"engine\":\"aksa-engine\",\"nonce_hmac\":\"{}\"}}",
                    compute_nonce_hmac(&t, nonce)
                )
            }
        });
        let lid = state.launch_id.clone();
        let manifest = format!(
            r#"{{"host":"127.0.0.1","port":{},"pid":7777,"version":"1.0.0","launch_id":"{}"}}"#,
            port, lid
        );
        let res = state.validate_and_sync_handshake(port, 7777, 7777, Some(&lid), Some(&manifest), token);
        assert_eq!(res, Ok(port));
        assert_eq!(state.get_state(), LifecycleState::Ready);
        assert_eq!(state.info.lock().unwrap().port, port);
    }

    #[test]
    fn test_ipc_cannot_elevate_to_ready_without_verified_handshake() {
        let state = SidecarState::new(0);
        let res = state.set_state_from_ipc(LifecycleState::Ready);
        assert!(res.is_err());
        assert_eq!(state.get_state(), LifecycleState::Starting);
    }
}
