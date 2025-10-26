let isControlling = false;
let currentDirection = {1: 1, 2: 1, 3: 1};
let timerInterval = null;
let controlStartTime = null;
let hasQueueWaiting = false;

// DOM Elements
const controlPanel = document.getElementById('control-panel');
const waitingPanel = document.getElementById('waiting-panel');
const statusMessage = document.getElementById('status-message');
const timerDisplay = document.getElementById('timer-display');
const queueInfo = document.getElementById('queue-info');
const queuePosition = document.getElementById('queue-position');
const queueMessage = document.getElementById('queue-message');

// Motor controls
const motors = [1, 2, 3];
const motorState = {
    1: {speed: 0, direction: 1, brake: 0},
    2: {speed: 0, direction: 1, brake: 0},
    3: {speed: 0, direction: 1, brake: 0}
};

// Debounce settings
const DEBOUNCE_MS = 250;
const debouncedSend = {};

function debounce(fn, wait) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), wait);
    };
}

// Socket will be initialized once the Socket.IO library is confirmed loaded
let socket = null;

function initSocketIfReady() {
    if (typeof window.io === 'undefined') {
        // Library not yet loaded; try again shortly
        return false;
    }
    if (socket) return true;
    // Initialize Socket.IO client (no auto-connect yet)
    // Force long-polling transport for compatibility with threading server on the Pi
    socket = io({
        autoConnect: false,
        transports: ['polling'],
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 500,
        timeout: 10000
    });

    // Register socket event handlers
    socket.on('connect', () => {
        console.log('Connected to server');
        statusMessage.textContent = 'Connected';
        statusMessage.style.color = '#666';
    });

    socket.on('connect_error', (err) => {
        console.error('Socket connect_error:', err);
        statusMessage.textContent = 'Connection failed';
        statusMessage.style.color = '#dc3545';
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        statusMessage.textContent = 'Disconnected';
        isControlling = false;
        updateUIState();
    });

    socket.on('control_granted', (data) => {
        console.log('Control granted:', data);
        isControlling = true;
        controlStartTime = Date.now();
        updateUIState();
        // Timer will be started based on hasQueueWaiting status in startTimer()
        startTimer();
    });

    socket.on('queued', (data) => {
        console.log('Queued:', data);
        isControlling = false;
        queuePosition.textContent = `Position: ${data.position}`;
        updateUIState();
    });

    socket.on('status_update', (data) => {
        console.log('Status update:', data);
        isControlling = data.controlling;
        hasQueueWaiting = data.queue_length > 1;
        
        if (data.controlling) {
            if (controlStartTime === null) {
                controlStartTime = Date.now();
            }
            startTimer();
            updateUIState();  // Update UI state to enable controls
        } else {
            stopTimer();
            queuePosition.textContent = `Position: ${data.position}`;
            updateUIState();  // Update UI state to disable controls
        }
    });

    socket.on('queue_update', (data) => {
        hasQueueWaiting = data.queue_length > 1;
        queueInfo.textContent = `Queue: ${data.queue_length}`;
        
        if (isControlling) {
            if (data.queue_length > 1) {
                startTimer();
            } else {
                stopTimer();
                timerDisplay.textContent = 'No time limit';
            }
        }
    });

    socket.on('timeout', (data) => {
        console.log('Timeout:', data);
        alert('Your time is up! You have been moved to the back of the queue.');
        isControlling = false;
        stopTimer();
        updateUIState();
    });

    socket.on('motor_updated', (data) => {
        console.log('Motor updated:', data);
        const { motor_id, speed, direction, brake } = data;
        // Update local view so spectators see live state
        if (motors.includes(motor_id)) {
            motorState[motor_id].speed = speed;
            motorState[motor_id].direction = direction;
            motorState[motor_id].brake = brake;
            // Reflect into controls
            const speedSlider = document.getElementById(`speed${motor_id}`);
            const speedValue = document.getElementById(`speed${motor_id}-value`);
            if (speedSlider) speedSlider.value = speed;
            if (speedValue) speedValue.textContent = speed;
            const dirButtons = document.querySelectorAll(`[data-motor="${motor_id}"]`);
            dirButtons.forEach(b => b.classList.toggle('active', parseInt(b.dataset.dir) === direction));
            const brakeBtn = document.getElementById(`brakeBtn${motor_id}`);
            if (brakeBtn) brakeBtn.setAttribute('aria-pressed', String(brake >= 1));
        }
    });

    socket.on('all_stopped', () => {
        console.log('All motors stopped');
    });

    // Receive full state snapshot (on connect and stop-all/timeout)
    socket.on('motor_state', (payload) => {
        const state = payload && payload.state ? payload.state : {};
        motors.forEach(motorId => {
            const s = state[motorId];
            if (!s) return;
            motorState[motorId] = { ...motorState[motorId], ...s };
            // Update UI elements
            const speedSlider = document.getElementById(`speed${motorId}`);
            const speedValue = document.getElementById(`speed${motorId}-value`);
            if (speedSlider) speedSlider.value = s.speed;
            if (speedValue) speedValue.textContent = s.speed;
            const dirButtons = document.querySelectorAll(`[data-motor="${motorId}"]`);
            dirButtons.forEach(b => b.classList.toggle('active', parseInt(b.dataset.dir) === s.direction));
            const brakeBtn = document.getElementById(`brakeBtn${motorId}`);
            if (brakeBtn) brakeBtn.setAttribute('aria-pressed', String(s.brake >= 1));
        });
    });

    socket.on('reconnect_attempt', (n) => {
        statusMessage.textContent = 'Reconnecting…';
        statusMessage.style.color = '#ffc107';
    });

    socket.on('reconnect', () => {
        statusMessage.textContent = 'Connected';
        statusMessage.style.color = '#666';
    });

    // Now connect after handlers are registered
    socket.connect();

    // Fallback: if still not connected after 10s, update status and attempt reconnect
    setTimeout(() => {
        try {
            if (!socket.connected) {
                statusMessage.textContent = 'Connection failed';
                statusMessage.style.color = '#dc3545';
                // Attempt a reconnect once
                socket.connect();
            }
        } catch (e) {
            console.error('Connection watchdog error:', e);
        }
    }, 10000);

    return true;
}

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
    statusMessage.textContent = 'Connected';
    statusMessage.style.color = '#666';
});

socket.on('connect_error', (err) => {
    console.error('Socket connect_error:', err);
    statusMessage.textContent = 'Connection failed';
    statusMessage.style.color = '#dc3545';
});

socket.on('reconnect_attempt', (n) => {
    statusMessage.textContent = 'Reconnecting…';
    statusMessage.style.color = '#ffc107';
});

socket.on('reconnect', () => {
    statusMessage.textContent = 'Connected';
    statusMessage.style.color = '#666';
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    statusMessage.textContent = 'Disconnected';
    isControlling = false;
    updateUIState();
});

socket.on('control_granted', (data) => {
    console.log('Control granted:', data);
    isControlling = true;
    controlStartTime = Date.now();
    updateUIState();
    // Timer will be started based on hasQueueWaiting status in startTimer()
    startTimer();
});

socket.on('queued', (data) => {
    console.log('Queued:', data);
    isControlling = false;
    queuePosition.textContent = `Position: ${data.position}`;
    updateUIState();
});

socket.on('status_update', (data) => {
    console.log('Status update:', data);
    isControlling = data.controlling;
    hasQueueWaiting = data.queue_length > 1;
    
    if (data.controlling) {
        if (controlStartTime === null) {
            controlStartTime = Date.now();
        }
        startTimer();
        updateUIState();  // Update UI state to enable controls
    } else {
        stopTimer();
        queuePosition.textContent = `Position: ${data.position}`;
        updateUIState();  // Update UI state to disable controls
    }
});

socket.on('queue_update', (data) => {
    hasQueueWaiting = data.queue_length > 1;
    queueInfo.textContent = `Queue: ${data.queue_length}`;
    
    if (isControlling) {
        if (data.queue_length > 1) {
            startTimer();
        } else {
            stopTimer();
            timerDisplay.textContent = 'No time limit';
        }
    }
});

socket.on('timeout', (data) => {
    console.log('Timeout:', data);
    alert('Your time is up! You have been moved to the back of the queue.');
    isControlling = false;
    stopTimer();
    updateUIState();
});

socket.on('motor_updated', (data) => {
    console.log('Motor updated:', data);
    const { motor_id, speed, direction, brake } = data;
    // Update local view so spectators see live state
    if (motors.includes(motor_id)) {
        motorState[motor_id].speed = speed;
        motorState[motor_id].direction = direction;
        motorState[motor_id].brake = brake;
        // Reflect into controls
        const speedSlider = document.getElementById(`speed${motor_id}`);
        const speedValue = document.getElementById(`speed${motor_id}-value`);
        if (speedSlider) speedSlider.value = speed;
        if (speedValue) speedValue.textContent = speed;
        const dirButtons = document.querySelectorAll(`[data-motor="${motor_id}"]`);
        dirButtons.forEach(b => b.classList.toggle('active', parseInt(b.dataset.dir) === direction));
        const brakeBtn = document.getElementById(`brakeBtn${motor_id}`);
        if (brakeBtn) brakeBtn.setAttribute('aria-pressed', String(brake >= 1));
    }
});

socket.on('all_stopped', () => {
    console.log('All motors stopped');
});
// Receive full state snapshot (on connect and stop-all/timeout)
socket.on('motor_state', (payload) => {
    const state = payload && payload.state ? payload.state : {};
    motors.forEach(motorId => {
        const s = state[motorId];
        if (!s) return;
        motorState[motorId] = { ...motorState[motorId], ...s };
        // Update UI elements
        const speedSlider = document.getElementById(`speed${motorId}`);
        const speedValue = document.getElementById(`speed${motorId}-value`);
        if (speedSlider) speedSlider.value = s.speed;
        if (speedValue) speedValue.textContent = s.speed;
        const dirButtons = document.querySelectorAll(`[data-motor="${motorId}"]`);
        dirButtons.forEach(b => b.classList.toggle('active', parseInt(b.dataset.dir) === s.direction));
        const brakeBtn = document.getElementById(`brakeBtn${motorId}`);
        if (brakeBtn) brakeBtn.setAttribute('aria-pressed', String(s.brake >= 1));
    });
});

socket.on('error', (data) => {
    console.error('Error:', data.message);
    alert(data.message);
});

// UI Functions
function updateUIState() {
    if (isControlling) {
        controlPanel.classList.remove('disabled');
        waitingPanel.classList.remove('active');
        statusMessage.textContent = 'You have control!';
        statusMessage.style.color = '#28a745';
    } else {
        controlPanel.classList.add('disabled');
        waitingPanel.classList.add('active');
        statusMessage.textContent = 'Waiting for your turn...';
        statusMessage.style.color = '#ffc107';
    }
}

function startTimer() {
    if (!hasQueueWaiting) {
        timerDisplay.textContent = 'No time limit';
        return;
    }
    
    stopTimer();
    
    timerInterval = setInterval(() => {
        if (controlStartTime === null) return;
        
        const elapsed = Date.now() - controlStartTime;
        const remaining = Math.max(0, 120000 - elapsed); // 120 seconds = 120000ms
        
        const minutes = Math.floor(remaining / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);
        
        timerDisplay.textContent = `Time: ${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (remaining === 0) {
            stopTimer();
        }
    }, 100);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    timerDisplay.textContent = '';
}

function sendMotorControl(motorId) {
    const state = motorState[motorId];
    socket.emit('motor_control', {
        motor_id: motorId,
        speed: state.speed,
        direction: state.direction,
        brake: state.brake
    });
}

// Setup motor control event listeners
motors.forEach(motorId => {
    // Create a debounced sender per motor
    debouncedSend[motorId] = debounce(() => sendMotorControl(motorId), DEBOUNCE_MS);

    // Speed slider
    const speedSlider = document.getElementById(`speed${motorId}`);
    const speedValue = document.getElementById(`speed${motorId}-value`);
    if (speedSlider && speedValue) {
        speedSlider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            speedValue.textContent = value;
            motorState[motorId].speed = value;
            // Debounced send for speed changes
            debouncedSend[motorId]();
        });
    }

    // Brake hold button
    const brakeBtn = document.getElementById(`brakeBtn${motorId}`);
    if (brakeBtn) {
        const press = (e) => {
            e.preventDefault();
            brakeBtn.setAttribute('aria-pressed', 'true');
            motorState[motorId].brake = 100; // apply brake fully while held
            sendMotorControl(motorId); // send immediately for responsiveness
        };
        const release = (e) => {
            e.preventDefault();
            brakeBtn.setAttribute('aria-pressed', 'false');
            motorState[motorId].brake = 0; // release brake when not held
            sendMotorControl(motorId);
        };
        // Pointer events (works for mouse + touch)
        brakeBtn.addEventListener('pointerdown', press);
        brakeBtn.addEventListener('pointerup', release);
        brakeBtn.addEventListener('pointerleave', release);
        brakeBtn.addEventListener('pointercancel', release);
        brakeBtn.addEventListener('lostpointercapture', release);
        // Keyboard accessibility (Space/Enter)
        brakeBtn.addEventListener('keydown', (e) => {
            if (e.code === 'Space' || e.code === 'Enter') press(e);
        });
        brakeBtn.addEventListener('keyup', (e) => {
            if (e.code === 'Space' || e.code === 'Enter') release(e);
        });
    }
    
    // Direction buttons
    const dirButtons = document.querySelectorAll(`[data-motor="${motorId}"]`);
    if (dirButtons && dirButtons.length) {
        dirButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const direction = parseInt(btn.dataset.dir);
                
                // Update button states
                dirButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // Update state and send
                motorState[motorId].direction = direction;
                sendMotorControl(motorId);
            });
        });
    }
});

// Stop all button
document.getElementById('stop-all-btn').addEventListener('click', () => {
    // Reset all sliders
    motors.forEach(motorId => {
    const s = document.getElementById(`speed${motorId}`);
    const sv = document.getElementById(`speed${motorId}-value`);
    if (s) s.value = 0;
    if (sv) sv.textContent = 0;
        
        motorState[motorId].speed = 0;
    motorState[motorId].brake = 0;
    const brakeBtn = document.getElementById(`brakeBtn${motorId}`);
    if (brakeBtn) brakeBtn.setAttribute('aria-pressed', 'false');
    });
    
    socket.emit('stop_all');
});

// Initialize UI
updateUIState();

// Defer socket init until Socket.IO client library is available
(function waitForSocketIOLibrary(attemptsLeft = 50) { // ~10s total at 200ms interval
    if (initSocketIfReady()) return;
    if (attemptsLeft <= 0) {
        statusMessage.textContent = 'Socket library not loaded';
        statusMessage.style.color = '#dc3545';
        return;
    }
    setTimeout(() => waitForSocketIOLibrary(attemptsLeft - 1), 200);
})();

// Fallback: if still not connected after 5s, update status and attempt reconnect
setTimeout(() => {
    try {
        if (!socket.connected) {
            statusMessage.textContent = 'Connection failed';
            statusMessage.style.color = '#dc3545';
            // Attempt a reconnect once
            socket.connect();
        }
    } catch (e) {
        console.error('Connection watchdog error:', e);
    }
}, 5000);
