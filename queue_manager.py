import time
from collections import deque
from threading import Lock

class QueueManager:
    def __init__(self, timeout_seconds=120):
        self.queue = deque()
        self.timeout_seconds = timeout_seconds
        self.user_start_times = {}
        self.lock = Lock()
    
    def add_user(self, user_id):
        """Add a user to the queue. Returns position (0 if controlling, 1+ if waiting)"""
        with self.lock:
            if user_id in self.queue:
                return self.queue.index(user_id)
            
            self.queue.append(user_id)
            position = len(self.queue) - 1
            
            if position == 0:
                self.user_start_times[user_id] = time.time()
            
            return position
    
    def remove_user(self, user_id):
        """Remove a user from the queue"""
        with self.lock:
            if user_id in self.queue:
                self.queue.remove(user_id)
            
            if user_id in self.user_start_times:
                del self.user_start_times[user_id]
    
    def is_controlling(self, user_id):
        """Check if a user is currently controlling"""
        with self.lock:
            return len(self.queue) > 0 and self.queue[0] == user_id
    
    def get_current_controller(self):
        """Get the current controlling user ID"""
        with self.lock:
            if len(self.queue) > 0:
                return self.queue[0]
            return None
    
    def get_position(self, user_id):
        """Get a user's position in queue (0 = controlling)"""
        with self.lock:
            if user_id in self.queue:
                return self.queue.index(user_id)
            return -1
    
    def get_queue_length(self):
        """Get total number of users in queue"""
        with self.lock:
            return len(self.queue)
    
    def check_timeout(self):
        """
        Check if current controller has timed out.
        Returns the user_id that was timed out, or None.
        Only times out if there are other users waiting.
        """
        with self.lock:
            if len(self.queue) < 2:
                # No one waiting, no timeout
                return None
            
            current_controller = self.queue[0]
            if current_controller not in self.user_start_times:
                return None
            
            elapsed = time.time() - self.user_start_times[current_controller]
            
            if elapsed >= self.timeout_seconds:
                # Timeout! Move to back of queue
                self.queue.rotate(-1)
                
                # Set start time for new controller
                new_controller = self.queue[0]
                self.user_start_times[new_controller] = time.time()
                
                # Clear old controller's start time
                if current_controller in self.user_start_times:
                    del self.user_start_times[current_controller]
                
                return current_controller
            
            return None
    
    def get_time_remaining(self, user_id):
        """Get time remaining for current controller (in seconds)"""
        with self.lock:
            if not self.is_controlling(user_id):
                return None
            
            if len(self.queue) < 2:
                # No timeout if no one waiting
                return None
            
            if user_id not in self.user_start_times:
                return self.timeout_seconds
            
            elapsed = time.time() - self.user_start_times[user_id]
            remaining = self.timeout_seconds - elapsed
            return max(0, remaining)
