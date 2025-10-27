// XCOM System File Transfer UI
(function(){
  const fileInput = document.getElementById('fileInput');
  const fileInfo = document.getElementById('fileInfo');
  const sendDataBtn = document.getElementById('sendDataBtn');
  const statusModal = document.getElementById('statusModal');
  const modalMessage = document.getElementById('modalMessage');
  const connectionStatus = document.getElementById('connectionStatus');

  const WS_URL = 'ws://127.0.0.1:8765';
  let ws = null;
  let connectionTimeout = null;

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
      };

      ws.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          if (response.type === 'connection_status') {
            if (response.connected) {
              updateConnectionStatus('STM32 device connected', false);
              resolve();
            } else {
              updateConnectionStatus('STM32 device not found', true);
              reject('STM32 device not found');
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
        ws = null;
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

  sendDataBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;

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
