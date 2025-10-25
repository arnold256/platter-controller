from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
from queue_manager import QueueManager
from motor_controller import MotorController
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
# Use threading async mode for compatibility on Windows and enable verbose logs
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
)

motor_controller = MotorController()
queue_manager = QueueManager(timeout_seconds=120)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect(auth=None):
    client_id = request.sid
    position = queue_manager.add_user(client_id)
    
    print(f"User {client_id} connected at position {position}")
    
    if position == 0:
        print(f"Granting control to {client_id}")
        emit('control_granted', {'message': 'You have control'})
        emit('status_update', {
            'controlling': True,
            'position': 0,
            'queue_length': queue_manager.get_queue_length()
        })
    else:
        print(f"Queuing {client_id} at position {position}")
        emit('queued', {
            'position': position,
            'message': f'You are #{position} in queue'
        })
        emit('status_update', {
            'controlling': False,
            'position': position,
            'queue_length': queue_manager.get_queue_length()
        })
    
    # Broadcast queue update to all clients
    socketio.emit('queue_update', {
        'queue_length': queue_manager.get_queue_length()
    })

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    was_controlling = queue_manager.is_controlling(client_id)
    queue_manager.remove_user(client_id)
    
    if was_controlling:
        # Stop all motors when user disconnects
        motor_controller.stop_all()
        
        # Give control to next user
        next_user = queue_manager.get_current_controller()
        if next_user:
            socketio.emit('control_granted', {
                'message': 'You have control'
            }, room=next_user)
            socketio.emit('status_update', {
                'controlling': True,
                'position': 0,
                'queue_length': queue_manager.get_queue_length()
            }, room=next_user)
    
    # Update all clients about queue status
    socketio.emit('queue_update', {
        'queue_length': queue_manager.get_queue_length()
    })

@socketio.on('motor_control')
def handle_motor_control(data):
    client_id = request.sid
    
    if not queue_manager.is_controlling(client_id):
        emit('error', {'message': 'You do not have control'})
        return
    
    motor_id = data.get('motor_id')
    speed = data.get('speed', 0)
    direction = data.get('direction', 0)
    brake = data.get('brake', 0)
    
    if motor_id in [1, 2, 3]:
        motor_controller.set_motor(motor_id, speed, direction, brake)
        emit('motor_updated', {
            'motor_id': motor_id,
            'speed': speed,
            'direction': direction,
            'brake': brake
        })

@socketio.on('stop_all')
def handle_stop_all():
    client_id = request.sid
    
    if not queue_manager.is_controlling(client_id):
        emit('error', {'message': 'You do not have control'})
        return
    
    motor_controller.stop_all()
    emit('all_stopped', {})

def check_timeouts():
    """Background thread to check for user timeouts"""
    while True:
        time.sleep(1)
        
        timed_out_user = queue_manager.check_timeout()
        if timed_out_user:
            # Stop all motors
            motor_controller.stop_all()
            
            # Notify timed out user
            socketio.emit('timeout', {
                'message': 'Your time is up'
            }, room=timed_out_user)
            
            socketio.emit('status_update', {
                'controlling': False,
                'position': queue_manager.get_position(timed_out_user),
                'queue_length': queue_manager.get_queue_length()
            }, room=timed_out_user)
            
            # Give control to next user
            next_user = queue_manager.get_current_controller()
            if next_user:
                socketio.emit('control_granted', {
                    'message': 'You have control'
                }, room=next_user)
                
                socketio.emit('status_update', {
                    'controlling': True,
                    'position': 0,
                    'queue_length': queue_manager.get_queue_length()
                }, room=next_user)
            
            # Update all clients
            socketio.emit('queue_update', {
                'queue_length': queue_manager.get_queue_length()
            })

if __name__ == '__main__':
    # Start timeout checker thread
    timeout_thread = threading.Thread(target=check_timeouts, daemon=True)
    timeout_thread.start()
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    finally:
        motor_controller.cleanup()
