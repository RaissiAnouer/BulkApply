const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

// Set Windows AppUserModelId so Windows identifies the app as AutoApply in taskbar & notifications
if (process.platform === 'win32') {
  app.setAppUserModelId('com.autoapply.desktop');
}

// Ensure single running instance
const rootDir = path.resolve(__dirname, '..', '..');
const logFile = path.join(rootDir, 'desktop.log');

function log(msg) {
  try {
    const line = `[${new Date().toISOString()}] ${msg}\n`;
    fs.appendFileSync(logFile, line);
  } catch (e) {}
}

log('Electron main process started.');

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  log('Failed to obtain single instance lock. Quitting.');
  app.quit();
  process.exit(0);
}

let mainWindow = null;
let backendProcess = null;

const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');
const distHtml = path.join(frontendDir, 'dist', 'index.html');
const iconPath = path.join(frontendDir, 'public', 'icon.png');
const isDev = !app.isPackaged && process.env.NODE_ENV !== 'production';

// Resolve Python executable (prefers backend virtual environment)
function getPythonExecutable() {
  const venvPython = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return 'python';
}

// Fast check if an HTTP service endpoint is responding
function isUrlAvailable(url, timeoutMs = 800) {
  return new Promise((resolve) => {
    try {
      const parsed = new URL(url);
      const req = http.get(
        {
          hostname: parsed.hostname,
          port: parsed.port,
          path: parsed.pathname,
          timeout: timeoutMs,
        },
        (res) => {
          resolve(res.statusCode >= 200 && res.statusCode < 400);
        }
      );
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    } catch {
      resolve(false);
    }
  });
}

// Check if FastAPI backend is healthy with retry backoff
async function waitForBackend(retries = 30, delayMs = 600) {
  for (let attempt = 0; attempt < retries; attempt++) {
    const ready = await isUrlAvailable('http://127.0.0.1:8000/api/health', 800);
    if (ready) return true;
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

// Spawn FastAPI backend with windowsHide to avoid black console popups
function startBackend() {
  const pythonExe = getPythonExecutable();
  console.log(`[AutoApply Desktop] Starting backend via ${pythonExe}...`);

  backendProcess = spawn(
    pythonExe,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
    {
      cwd: backendDir,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      windowsHide: true,
      stdio: 'pipe',
    }
  );

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.log(`[Backend log] ${data.toString().trim()}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`[Backend exited with code ${code}]`);
    backendProcess = null;
  });
}

// Gracefully terminate backend
function stopBackend() {
  if (backendProcess) {
    console.log('[AutoApply Desktop] Shutting down backend process...');
    try {
      const req = http.request(
        {
          hostname: '127.0.0.1',
          port: 8000,
          path: '/api/system/shutdown',
          method: 'POST',
          timeout: 1000,
        },
        () => {}
      );
      req.on('error', () => {});
      req.end();
    } catch (e) {
      // ignore
    }

    const pid = backendProcess.pid;
    setTimeout(() => {
      try {
        if (process.platform === 'win32' && pid) {
          spawn('taskkill', ['/pid', String(pid), '/f', '/t'], { windowsHide: true });
        } else if (backendProcess && !backendProcess.killed) {
          backendProcess.kill('SIGTERM');
        }
      } catch (e) {
        // ignore
      }
    }, 1200);
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    center: true,
    title: 'AutoApply — Automated Job Application Suite',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    backgroundColor: '#0f172a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false, // Allows seamless file:// to localhost:8000 API requests
    },
  });

  // Attach ready-to-show before loading URL so the event is never missed
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Remove default archaic Electron browser menu bar for a clean native look
  Menu.setApplicationMenu(null);

  // Keyboard accelerators
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F5' || (input.control && input.key.toLowerCase() === 'r')) {
      mainWindow.reload();
      event.preventDefault();
    }
    if (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i')) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  // Determine target URL: Vite dev server or compiled production dist
  const viteAvailable = await isUrlAvailable('http://localhost:5173', 500);

  if (isDev && viteAvailable) {
    console.log('[AutoApply Desktop] Loading from active Vite dev server (http://localhost:5173)...');
    await mainWindow.loadURL('http://localhost:5173');
  } else if (fs.existsSync(distHtml)) {
    console.log('[AutoApply Desktop] Loading compiled production interface from dist/index.html...');
    await mainWindow.loadFile(distHtml);
  } else {
    console.log('[AutoApply Desktop] Loading interface...');
    try {
      await mainWindow.loadURL('http://localhost:5173');
    } catch {
      if (fs.existsSync(distHtml)) {
        await mainWindow.loadFile(distHtml);
      }
    }
  }

  if (mainWindow && !mainWindow.isVisible()) {
    mainWindow.show();
  }

  // Window control IPC handlers
  ipcMain.on('app-close', () => {
    if (mainWindow) mainWindow.close();
  });
  ipcMain.on('app-minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });
  ipcMain.on('app-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Handle second instance activation
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(async () => {
  log('app.whenReady reached.');
  // Check if FastAPI backend is already running
  const alreadyRunning = await isUrlAvailable('http://127.0.0.1:8000/api/health', 400);
  if (!alreadyRunning) {
    log('Backend not running. Spawning backend...');
    startBackend();
    const ready = await waitForBackend(25, 500);
    log(`Backend wait complete. Ready: ${ready}`);
  } else {
    log('Backend already active on port 8000.');
  }

  log('Creating main desktop window...');
  await createWindow();
  log('Main desktop window created successfully.');

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});
