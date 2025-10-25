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
    1: {speed: 0, direction: 1, brake: 100},
    2: {speed: 0, direction: 1, brake: 100},
    3: {speed: 0, direction: 1, brake: 100}
};

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
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
});

socket.on('all_stopped', () => {
    console.log('All motors stopped');
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
    // Speed slider
    const speedSlider = document.getElementById(`speed${motorId}`);
    const speedValue = document.getElementById(`speed${motorId}-value`);
    
    speedSlider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        speedValue.textContent = value;
        motorState[motorId].speed = value;
        sendMotorControl(motorId);
    });
    
    // Brake slider
    const brakeSlider = document.getElementById(`brake${motorId}`);
    const brakeValue = document.getElementById(`brake${motorId}-value`);
    
    brakeSlider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        brakeValue.textContent = value;
        motorState[motorId].brake = value;
        sendMotorControl(motorId);
    });
    
    // Direction buttons
    const dirButtons = document.querySelectorAll(`[data-motor="${motorId}"]`);
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
});

// Stop all button
document.getElementById('stop-all-btn').addEventListener('click', () => {
    // Reset all sliders
    motors.forEach(motorId => {
        document.getElementById(`speed${motorId}`).value = 0;
        document.getElementById(`speed${motorId}-value`).textContent = 0;
        document.getElementById(`brake${motorId}`).value = 100;
        document.getElementById(`brake${motorId}-value`).textContent = 100;
        
        motorState[motorId].speed = 0;
        motorState[motorId].brake = 100;
    });
    
    socket.emit('stop_all');
});

// Initialize UI
updateUIState();

// Initialize socket connection AFTER all handlers are set up
const socket = io();
