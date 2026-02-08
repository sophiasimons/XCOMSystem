// XCOM System File Reception UI
(function(){
  const statusModal = document.getElementById('statusModal');
  const modalMessage = document.getElementById('modalMessage');
  const statusDot = document.querySelector('.status-dot');
  const statusText = document.querySelector('.status-text');

  const WS_URL = 'ws://127.0.0.1:8766'; // Note: Different port from TX
  let ws = null;
  let connectionTimeout = null;
  let connectionCheckInterval = null;

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

  // Update the connection status display (removed - now only using top indicator)
  function updateConnectionStatus(status, isError = false) {
    // No-op: Center status removed, using only top-right indicator
  }

  // Update the connection indicator
  function updateConnectionIndicator(isConnected, message) {
    statusDot.className = 'status-dot ' + (isConnected ? 'connected' : 'disconnected');
    statusText.textContent = message;
  }

  // Start periodic connection checking
  function startConnectionMonitoring() {
    if (connectionCheckInterval) {
      clearInterval(connectionCheckInterval);
    }

    connectionCheckInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'check_connection' }));
      } else {
        updateConnectionIndicator(false, 'Disconnected');
        connectToDevice().catch(() => {
          updateConnectionIndicator(false, 'Connection failed');
        });
      }
    }, 2000); // Changed from 5000ms to 2000ms for faster updates
  }

  // Connect to WebSocket and check STM32 connection
  async function connectToDevice() {
    return new Promise((resolve, reject) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'check_connection' }));
        return;
      }

      try {
        ws = new WebSocket(WS_URL);
      } catch(e) {
        reject('Could not connect to WebSocket server');
        return;
      }

      connectionTimeout = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          reject('Connection timeout');
        }
      }, 5000);

      ws.onopen = () => {
        console.log('WebSocket connected successfully to RX bridge');
        clearTimeout(connectionTimeout);
        ws.send(JSON.stringify({ type: 'check_connection' }));
        startConnectionMonitoring();
      };

      ws.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          console.log('Received message:', response);
          if (response.type === 'connection_status') {
            if (response.connected) {
              const deviceInfo = response.reason || `STM32 RX Connected (port ${response.port})`;
              console.log('Connection status: Connected -', deviceInfo);
              updateConnectionStatus(deviceInfo, false);
              updateConnectionIndicator(true, deviceInfo);
              resolve();
            } else {
              const errorMsg = response.reason || 'Not Ready - No STM32 connected';
              console.log('Connection status: Not Ready -', errorMsg);
              updateConnectionStatus(errorMsg, true);
              updateConnectionIndicator(false, errorMsg);
              // Don't reject - keep checking in the background
            }
          } else if (response.type === 'data_received') {
            // Handle incoming data here
            showToast('New data received');
            // TODO: Process and display the received data
          }
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      };

      ws.onclose = () => {
        updateConnectionStatus('Connection lost', true);
        updateConnectionIndicator(false, 'Connection lost');
        ws = null;
        
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

  // Show toast notification
  function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }

  // Initial connection
  console.log('Initializing WebSocket connection to RX bridge:', WS_URL);
  connectToDevice().catch(error => {
    console.error('Initial connection failed:', error);
    updateConnectionStatus(error, true);
  });

  window.addEventListener('beforeunload', () => { 
    if (ws) ws.close(); 
    if (connectionCheckInterval) clearInterval(connectionCheckInterval);
  });
})();