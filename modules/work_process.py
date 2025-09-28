# modules/work_process.py - Work Process Management

import asyncio
import random
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

class ProcessStatus(Enum):
    IDLE = "idle"
    GETTING_READY = "getting_ready"
    LOAD_EGGS = "load_eggs"
    READY_TO_PROCESS = "ready_to_process"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class WorkProcessManager:
    def __init__(self):
        # Process state
        self.current_status = ProcessStatus.IDLE
        self.current_batch = None
        self.processing_stats = {
            "totalProcessed": 0,
            "goodEggs": 0,
            "badEggs": 0,
            "smallEggs": 0,
            "mediumEggs": 0,
            "largeEggs": 0
        }
        
        # Process configuration
        self.process_config = {
            "getting_ready_delay": (2.0, 3.0),
            "load_eggs_delay": (3.0, 4.0),
            "processing_delay": (5.0, 8.0),
            "egg_processing_rate": 0.8,  # eggs per second
            "success_rate": 0.95  # 95% success rate for individual eggs
        }
        
        # Component readiness status
        self.component_status = {
            "UNO": False,
            "HX711": False,
            "NEMA23": False,
            "SG90": False,
            "MG996R": False
        }
        
        # Active process tracking
        self.is_processing = False
        self.current_egg_count = 0
        self.target_egg_count = 0
    
    def update_component_status(self, component: str, ready: bool) -> None:
        """Update component readiness status"""
        if component in self.component_status:
            self.component_status[component] = ready
            print(f"🔧 {component} status: {'Ready' if ready else 'Not Ready'}")
    
    def are_all_components_ready(self) -> bool:
        """Check if all components are ready for processing"""
        return all(self.component_status.values())
    
    def can_start_processing(self) -> bool:
        """Check if processing can be started"""
        return (self.current_status == ProcessStatus.IDLE and 
                self.are_all_components_ready() and 
                not self.is_processing)
    
    def start_batch(self, batch_id: str, egg_count: int = 10) -> Dict[str, Any]:
        """Start a new processing batch"""
        if not self.can_start_processing():
            return {
                "success": False,
                "message": "Cannot start processing. Check component readiness or current status.",
                "status": self.current_status.value
            }
        
        self.current_batch = {
            "id": batch_id,
            "start_time": datetime.now().isoformat(),
            "target_count": egg_count
        }
        
        self.current_status = ProcessStatus.GETTING_READY
        self.current_egg_count = 0
        self.target_egg_count = egg_count
        
        # Reset processing stats for new batch
        self.processing_stats = {
            "totalProcessed": 0,
            "goodEggs": 0,
            "badEggs": 0,
            "smallEggs": 0,
            "mediumEggs": 0,
            "largeEggs": 0
        }
        
        print(f"🚀 Started batch {batch_id} with {egg_count} eggs")
        
        return {
            "success": True,
            "message": f"Batch {batch_id} started successfully",
            "batch": self.current_batch,
            "status": self.current_status.value
        }
    
    async def execute_work_process(self, send_callback) -> Dict[str, Any]:
        """Execute the complete work process simulation"""
        if not self.current_batch:
            return {
                "success": False,
                "message": "No active batch to process"
            }
        
        try:
            self.is_processing = True
            
            # Phase 1: Getting Ready
            await self._phase_getting_ready(send_callback)
            
            # Phase 2: Load Eggs
            await self._phase_load_eggs(send_callback)
            
            # Phase 3: Ready to Process
            await self._phase_ready_to_process(send_callback)
            
            # Phase 4: Processing
            await self._phase_processing(send_callback)
            
            # Phase 5: Completed
            await self._phase_completed(send_callback)
            
            return {
                "success": True,
                "message": "Work process completed successfully",
                "stats": self.processing_stats,
                "batch": self.current_batch
            }
            
        except Exception as e:
            print(f"❌ Error in work process: {e}")
            self.current_status = ProcessStatus.ERROR
            await send_callback({
                "type": "process_update",
                "status": self.current_status.value,
                "message": f"Process error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            return {
                "success": False,
                "message": f"Process error: {str(e)}"
            }
        finally:
            self.is_processing = False
    
    async def _phase_getting_ready(self, send_callback) -> None:
        """Phase 1: Getting ready for processing"""
        self.current_status = ProcessStatus.GETTING_READY
        
        await send_callback({
            "type": "process_update",
            "status": self.current_status.value,
            "message": "System getting ready for processing...",
            "timestamp": datetime.now().isoformat()
        })
        
        delay = random.uniform(*self.process_config["getting_ready_delay"])
        await asyncio.sleep(delay)
        
        print("✅ System ready for processing")
    
    async def _phase_load_eggs(self, send_callback) -> None:
        """Phase 2: Loading eggs into system"""
        self.current_status = ProcessStatus.LOAD_EGGS
        
        await send_callback({
            "type": "process_update",
            "status": self.current_status.value,
            "message": f"Loading {self.target_egg_count} eggs into processing system...",
            "timestamp": datetime.now().isoformat()
        })
        
        delay = random.uniform(*self.process_config["load_eggs_delay"])
        await asyncio.sleep(delay)
        
        print(f"✅ Loaded {self.target_egg_count} eggs")
    
    async def _phase_ready_to_process(self, send_callback) -> None:
        """Phase 3: Ready to start processing"""
        self.current_status = ProcessStatus.READY_TO_PROCESS
        
        await send_callback({
            "type": "process_update",
            "status": self.current_status.value,
            "message": "System ready to process eggs. Starting processing...",
            "timestamp": datetime.now().isoformat()
        })
        
        await asyncio.sleep(1.0)  # Brief pause before processing
        print("✅ Ready to process eggs")
    
    async def _phase_processing(self, send_callback) -> None:
        """Phase 4: Processing eggs"""
        self.current_status = ProcessStatus.PROCESSING
        
        await send_callback({
            "type": "process_update",
            "status": self.current_status.value,
            "message": "Processing eggs...",
            "timestamp": datetime.now().isoformat()
        })
        
        # Simulate processing each egg
        for i in range(self.target_egg_count):
            await self._process_single_egg(send_callback, i + 1)
            
            # Send progress update every few eggs
            if (i + 1) % 3 == 0 or (i + 1) == self.target_egg_count:
                await send_callback({
                    "type": "process_progress",
                    "current": i + 1,
                    "total": self.target_egg_count,
                    "stats": self.processing_stats.copy(),
                    "timestamp": datetime.now().isoformat()
                })
        
        print(f"✅ Processed {self.current_egg_count} eggs")
    
    async def _process_single_egg(self, send_callback, egg_number: int) -> None:
        """Process a single egg"""
        # Simulate processing time
        processing_time = 1.0 / self.process_config["egg_processing_rate"]
        await asyncio.sleep(processing_time)
        
        # Simulate egg analysis
        is_good = random.random() < self.process_config["success_rate"]
        size_category = random.choice(["small", "medium", "large"])
        
        # Update stats
        self.processing_stats["totalProcessed"] += 1
        self.current_egg_count += 1
        
        if is_good:
            self.processing_stats["goodEggs"] += 1
            self.processing_stats[f"{size_category}Eggs"] += 1
        else:
            self.processing_stats["badEggs"] += 1
        
        # Send individual egg result
        await send_callback({
            "type": "egg_result",
            "egg_number": egg_number,
            "result": {
                "quality": "good" if is_good else "bad",
                "size": size_category,
                "timestamp": datetime.now().isoformat()
            }
        })
    
    async def _phase_completed(self, send_callback) -> None:
        """Phase 5: Process completed"""
        self.current_status = ProcessStatus.COMPLETED
        
        completion_time = datetime.now().isoformat()
        if self.current_batch:
            self.current_batch["completion_time"] = completion_time
            self.current_batch["stats"] = self.processing_stats.copy()
        
        await send_callback({
            "type": "process_update",
            "status": self.current_status.value,
            "message": "Processing completed successfully!",
            "stats": self.processing_stats.copy(),
            "batch": self.current_batch,
            "timestamp": completion_time
        })
        
        print("✅ Work process completed")
    
    def stop_processing(self) -> Dict[str, Any]:
        """Stop current processing"""
        if not self.is_processing:
            return {
                "success": False,
                "message": "No active processing to stop"
            }
        
        self.is_processing = False
        self.current_status = ProcessStatus.IDLE
        
        print("🛑 Processing stopped")
        
        return {
            "success": True,
            "message": "Processing stopped",
            "stats": self.processing_stats.copy()
        }
    
    def reset_process(self) -> None:
        """Reset the work process to idle state"""
        self.current_status = ProcessStatus.IDLE
        self.current_batch = None
        self.is_processing = False
        self.current_egg_count = 0
        self.target_egg_count = 0
        
        # Reset stats
        self.processing_stats = {
            "totalProcessed": 0,
            "goodEggs": 0,
            "badEggs": 0,
            "smallEggs": 0,
            "mediumEggs": 0,
            "largeEggs": 0
        }
        
        print("🔄 Work process reset to idle")
    
    def get_process_status(self) -> Dict[str, Any]:
        """Get current process status"""
        return {
            "status": self.current_status.value,
            "is_processing": self.is_processing,
            "current_batch": self.current_batch,
            "stats": self.processing_stats.copy(),
            "component_status": self.component_status.copy(),
            "can_start": self.can_start_processing()
        }

