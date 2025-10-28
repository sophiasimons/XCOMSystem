// XCOM System File Transfer UI
(function(){
  const fileInput = document.getElementById('fileInput');
  const fileInfo = document.getElementById('fileInfo');
  const sendDataBtn = document.getElementById('sendDataBtn');
  const statusModal = document.getElementById('statusModal');
  const modalMessage = document.getElementById('modalMessage');
  const connectionStatus = document.getElementById('connectionStatus');
  const statusDot = document.querySelector('.status-dot');
  const statusText = document.querySelector('.status-text');

  const WS_URL = 'ws://127.0.0.1:8765';
  let ws = null;
  let connectionTimeout = null;
  let connectionCheckInterval = null;

  // Update the connection indicator
  function updateConnectionIndicator(isConnected, message) {
    statusDot.className = 'status-dot ' + (isConnected ? 'connected' : 'disconnected');
    statusText.textContent = message;
  }

  // Start periodic connection checking
  function startConnectionMonitoring() {
    // Clear any existing interval
    if (connectionCheckInterval) {
      clearInterval(connectionCheckInterval);
    }

    // Check connection status every 5 seconds
    connectionCheckInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'check_connection' }));
      } else {
        updateConnectionIndicator(false, 'Disconnected');
        connectToDevice().catch(() => {
          updateConnectionIndicator(false, 'Connection failed');
        });
      }
    }, 5000);
  }

  // Show/hide the status modal
  function showModal(message, showSpinner = true) {
    modalMessage.textContent = message;
    statusModal.classList.add('show');
    const spinner = statusModal.querySelector('.modal-spinner');
    spinner.style.display = showSpinner ? 'block' : 'none';
  }

  function hideModal() {
    statusModal.classList.remove('show');
  }

  // Update the connection status display
  function updateConnectionStatus(status, isError = false) {
    connectionStatus.textContent = status;
    connectionStatus.className = 'connection-status ' + (isError ? 'error' : 'success');
  }

  // Connect to WebSocket and check STM32 connection
  async function connectToDevice() {
    return new Promise((resolve, reject) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        // We're connected to WebSocket, now check STM32
        ws.send(JSON.stringify({ type: 'check_connection' }));
        return;
      }

      try {
        ws = new WebSocket(WS_URL);
      } catch(e) {
        reject('Could not connect to WebSocket server');
        return;
      }

      // Set connection timeout
      connectionTimeout = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          reject('Connection timeout');
        }
      }, 5000);

      ws.onopen = () => {
        clearTimeout(connectionTimeout);
        // Check STM32 connection once WebSocket is open
        ws.send(JSON.stringify({ type: 'check_connection' }));
        // Start monitoring the connection
        startConnectionMonitoring();
      };

      ws.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          if (response.type === 'connection_status') {
            if (response.connected) {
              const deviceInfo = `Connected (${response.port})`;
              updateConnectionStatus(deviceInfo, false);
              updateConnectionIndicator(true, deviceInfo);
              resolve();
            } else {
              const errorMsg = response.reason || 'Device not found';
              updateConnectionStatus(errorMsg, true);
              updateConnectionIndicator(false, errorMsg);
              reject(errorMsg);
            }
          } else if (response.type === 'upload_success') {
            updateConnectionStatus('File sent to STM32', false);
          } else if (response.type === 'error') {
            updateConnectionStatus(response.message, true);
            reject(response.message);
          }
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      };

      ws.onclose = () => {
        updateConnectionStatus('Connection lost', true);
        updateConnectionIndicator(false, 'Connection lost');
        ws = null;
        
        // Try to reconnect after a brief delay
        setTimeout(() => {
          connectToDevice().catch(() => {
            updateConnectionIndicator(false, 'Reconnection failed');
          });
        }, 3000);
      };

      ws.onerror = () => {
        clearTimeout(connectionTimeout);
        reject('Connection failed');
      };
    });
  }

  async function sendMessage(obj) {
    try {
      updateConnectionStatus('Connecting to device...', true);
      await connectToDevice();
      const envelope = { type: 'raw', data: JSON.stringify(obj) };
      ws.send(JSON.stringify(envelope));
      updateConnectionStatus('Device connected', false);
      return true;
    } catch (error) {
      updateConnectionStatus('Device not found', true);
      showModal('Device not found. Please check the connection.', false);
      setTimeout(hideModal, 3000);
      return false;
    }
  }

  // File upload handling
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) {
      fileInfo.textContent = '';
      sendDataBtn.disabled = true;
      return;
    }

    // File size validation (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB in bytes
    if (file.size > maxSize) {
      fileInfo.textContent = 'Error: File size exceeds 10MB limit';
      fileInfo.style.color = '#ff4d4f';
      sendDataBtn.disabled = true;
      return;
    }

    fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)}KB)`;
    fileInfo.style.color = 'var(--muted)';
    sendDataBtn.disabled = false;
  });

  // Show toast notification
  function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }

  sendDataBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) {
      showToast('Please select a file first');
      return;
    }

    showModal('Connecting to device...');

    try {
      const reader = new FileReader();
      reader.onload = async (e) => {
        const data = e.target.result;
        const message = {
          type: 'file_upload',
          filename: file.name,
          size: file.size,
          data: data
        };

        const sent = await sendMessage(message);
        if (sent) {
          // Reset the file input
          fileInput.value = '';
          fileInfo.textContent = 'File sent successfully';
          sendDataBtn.disabled = true;
          showModal('File sent successfully!', false);
          setTimeout(hideModal, 2000);
        }
      };
      reader.readAsDataURL(file);
    } catch (error) {
      fileInfo.textContent = 'Error sending file: ' + error.message;
      fileInfo.style.color = '#ff4d4f';
      showModal('Error sending file', false);
      setTimeout(hideModal, 3000);
    }
  });

  window.addEventListener('beforeunload', ()=>{ 
    if (ws) ws.close(); 
  });
})();
