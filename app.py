from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
from queue_manager import QueueManager
import config
from motor_controller import MotorController
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# Add CORS and cache headers
@app.after_request
def add_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Use threading async mode for compatibility on Windows and enable verbose logs
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    engineio_logger_level='INFO',
    # Cloudflare compatibility: use polling as primary since WebSocket may not work
    transports=['polling', 'websocket'],
)

motor_controller = MotorController()
queue_manager = QueueManager(timeout_seconds=120)

# Track current motor state to keep spectators in sync
current_motor_state = {
    1: {"speed": 0, "direction": 1, "brake": 0},
    2: {"speed": 0, "direction": 1, "brake": 0},
    3: {"speed": 0, "direction": 1, "brake": 0},
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect(auth=None):
    client_id = request.sid
    
    position = queue_manager.add_user(client_id)
    
    print(f"User {client_id} connected at position {position}", flush=True)
    
    if position == 0:
        print(f"Granting control to {client_id}", flush=True)
        emit('control_granted', {'message': 'You have control'})
        emit('status_update', {
            'controlling': True,
            'position': 0,
            'queue_length': queue_manager.get_queue_length()
        })
    else:
        print(f"Queuing {client_id} at position {position}", flush=True)
        emit('queued', {
            'position': position,
            'message': f'You are #{position} in queue'
        })
        emit('status_update', {
            'controlling': False,
            'position': position,
            'queue_length': queue_manager.get_queue_length()
        })
    
    # Send current motor state to this client so their UI reflects live values
    emit('motor_state', { 'state': current_motor_state })

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
    import sys
    # Write to a debug file as well to ensure it's captured
    with open('/tmp/motor_control_debug.log', 'a') as f:
        f.write(f"MOTOR_CONTROL_HANDLER_CALLED at {time.time()}\n")
        f.write(f"DATA: {data}\n")
        f.flush()
    
    print(f"MOTOR_CONTROL_HANDLER_CALLED", file=sys.stderr, flush=True)
    print(f"DATA_RECEIVED: {data}", file=sys.stderr, flush=True)
    
    client_id = request.sid
    print(f"CLIENT_ID: {client_id}", file=sys.stderr, flush=True)
    
    if not queue_manager.is_controlling(client_id):
        is_controlling = queue_manager.is_controlling(client_id)
        current_controller = queue_manager.get_current_controller()
        print(f"motor_control BLOCKED: client_id={client_id}, is_controlling={is_controlling}, current_controller={current_controller}", flush=True)
        emit('error', {'message': 'You do not have control'})
        return
    
    motor_id = data.get('motor_id')
    speed = data.get('speed', 0)
    direction = data.get('direction', 0)
    brake = data.get('brake', 0)
    
    print(f"motor_control received: m={motor_id} speed={speed} dir={direction} brake={brake}", flush=True)
    
    if motor_id in [1, 2, 3]:
        print(f"motor_control apply m={motor_id} speed={speed} dir={direction} brake={brake}", flush=True)
        try:
            print(f"calling motor_controller.set_motor...", flush=True)
            motor_controller.set_motor(motor_id, speed, direction, brake)
            print(f"set_motor returned successfully", flush=True)
        except Exception as e:
            print(f"motor_control error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            emit('error', {'message': f'Apply failed: {e}'})
            return
        # Update server-side snapshot
        current_motor_state[motor_id] = {
            'speed': speed,
            'direction': direction,
            'brake': brake
        }
        # Broadcast to all clients so spectators update their UI
        socketio.emit('motor_updated', {
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
    # Reflect stopped state in snapshot: speed=0, brake=100 (applied)
    for m in current_motor_state.keys():
        current_motor_state[m]['speed'] = 0
        current_motor_state[m]['brake'] = 100
    # Broadcast to all so everyone sees stopped state
    socketio.emit('motor_state', { 'state': current_motor_state })
    socketio.emit('all_stopped', {})

def check_timeouts():
    """Background thread to check for user timeouts"""
    while True:
        time.sleep(1)
        
        timed_out_user = queue_manager.check_timeout()
        if timed_out_user:
            # Stop all motors
            motor_controller.stop_all()
            for m in current_motor_state.keys():
                current_motor_state[m]['speed'] = 0
                current_motor_state[m]['brake'] = 100
            
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
                print(f"Granting control to next user: {next_user}", flush=True)
                socketio.emit('control_granted', {
                    'message': 'You have control'
                }, room=next_user)
                
                socketio.emit('status_update', {
                    'controlling': True,
                    'position': 0,
                    'queue_length': queue_manager.get_queue_length()
                }, room=next_user)
            else:
                print(f"No next user in queue", flush=True)
            
            # Update all clients
            socketio.emit('motor_state', { 'state': current_motor_state })
            socketio.emit('queue_update', {
                'queue_length': queue_manager.get_queue_length()
            })

if __name__ == '__main__':
    # Start timeout checker thread
    timeout_thread = threading.Thread(target=check_timeouts, daemon=True)
    timeout_thread.start()
    
    try:
        # Under systemd this uses Werkzeug in threading mode; allow explicitly
        socketio.run(
            app,
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            allow_unsafe_werkzeug=True,
        )
    finally:
        motor_controller.cleanup()
