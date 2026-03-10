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

  // Connect to WebSocket and check FPGA connection
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
        // Populate file list from the bridge's HTTP API so pre-existing files are shown
        // Fetch host path first so Show folder links can point to file:// when available
        getHostReceivedPath().finally(() => populateFileList());
      };

      ws.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          console.log('Received message:', response);
          if (response.type === 'connection_status') {
            if (response.connected) {
              // Prefer explicit device field from server; otherwise fall back to reason/port
              let deviceInfo = '';
              if (response.device === 'fpga') {
                deviceInfo = `FPGA Connected (port ${response.port})`;
              } else if (response.device === 'stm32') {
                deviceInfo = `STM32 RX Connected (port ${response.port})`;
              } else {
                deviceInfo = response.reason || `FPGA Connected (port ${response.port})`;
              }
              console.log('Connection status: Connected -', deviceInfo);
              updateConnectionStatus(deviceInfo, false);
              updateConnectionIndicator(true, deviceInfo);
              resolve();
            } else {
              const errorMsg = response.reason || 'Not Ready - No FPGA connected';
              console.log('Connection status: Not Ready -', errorMsg);
              updateConnectionStatus(errorMsg, true);
              updateConnectionIndicator(false, errorMsg);
              // Don't reject - keep checking in the background
            }
          } else if (response.type === 'data_received') {
            // Handle incoming data here
            showToast('New data received');
            // TODO: Process and display the received data
          } else if (response.type === 'file_received') {
            // Received a full file from the bridge (base64 payload)
            try {
              const filename = response.filename || ('received_' + Date.now() + '.bin');
              const size = response.size || 0;

              // Update UI file list
              addReceivedFile(filename, size);

              showToast('File received: ' + filename);
            } catch (e) {
              console.error('Error handling file_received:', e);
              showToast('Received file but failed to process');
            }
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

  // Add received file entry to the UI
  function addReceivedFile(filename, size) {
    const list = document.getElementById('fileList');
    if (!list) return;

    // avoid duplicates by scanning existing items' data-filename
    const existing = Array.from(list.querySelectorAll('[data-filename]')).some(el => el.getAttribute('data-filename') === filename);
    if (existing) return;

    const item = document.createElement('div');
    item.className = 'file-item';

    const meta = document.createElement('div');
    meta.className = 'file-meta';
    const name = document.createElement('div');
    name.className = 'file-name';
    name.textContent = filename;
    const sz = document.createElement('div');
    sz.className = 'file-size';
    sz.textContent = `${size} bytes`;
    meta.appendChild(name);
    meta.appendChild(sz);

    const actions = document.createElement('div');
    actions.className = 'file-actions';

    // Open/download button - links to files endpoint served by the bridge
    const open = document.createElement('a');
    open.className = 'btn';
    open.textContent = 'Open';
    open.href = `/files/${encodeURIComponent(filename)}`;
    open.target = '_blank';

  // Download button: explicitly instruct browser to download the file
  const download = document.createElement('a');
  download.className = 'btn';
  download.textContent = 'Download';
  download.href = `/files/${encodeURIComponent(filename)}`;
  // 'download' attribute suggests the browser download instead of navigate
  download.setAttribute('download', filename);

    // Show folder button - opens the files index or the host folder via file:// if available
    const folder = document.createElement('a');
    folder.className = 'btn secondary';
    folder.textContent = 'Show folder';
    folder.target = '_blank';
    if (hostReceivedPath) {
      // On macOS, file:// + absolute path opens Finder when the user clicks the link
      folder.href = 'file://' + encodeURI(hostReceivedPath);
    } else {
      folder.href = '/files/';
    }

  actions.appendChild(open);
  actions.appendChild(download);
  actions.appendChild(folder);

    item.appendChild(meta);
    item.appendChild(actions);
  item.setAttribute('data-filename', filename);

    // Prepend so newest appear first
    if (list.firstChild) list.insertBefore(item, list.firstChild);
    else list.appendChild(item);
  }

  // Host-side received_files path (file://) if provided by bridge
  let hostReceivedPath = '';

  function getHostReceivedPath() {
    return fetch('/api/host_received_path')
      .then(resp => {
        if (!resp.ok) return '';
        return resp.json();
      })
      .then(obj => {
        if (obj && obj.host_path) hostReceivedPath = obj.host_path;
        return hostReceivedPath;
      })
      .catch(() => '')
  }

  // Populate the file list by calling the bridge HTTP API
  function populateFileList() {
    fetch('/api/files')
      .then(resp => {
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.json();
      })
      .then(entries => {
        if (!Array.isArray(entries)) return;
        // Entries are expected newest-first; add each to the UI
        entries.forEach(ent => {
          addReceivedFile(ent.name, ent.size || 0);
        });
      })
      .catch(err => {
        console.debug('Could not populate file list:', err);
      });
  }

  window.addEventListener('beforeunload', () => { 
    if (ws) ws.close(); 
    if (connectionCheckInterval) clearInterval(connectionCheckInterval);
  });
})();