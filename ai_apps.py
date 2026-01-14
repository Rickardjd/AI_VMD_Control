"""
AI Application Definitions
Maps install IDs to human-readable names for i-PRO cameras
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class AIAppCategory(Enum):
    """Categories of AI applications"""
    VMD = "Video Motion Detection"
    PEOPLE = "People Detection"
    PEOPLE_COUNTING = "People Counting"
    FACE = "Face Detection"
    VEHICLE = "Vehicle Detection"
    LPR = "License Plate Recognition"


@dataclass
class AIApp:
    """AI Application definition"""
    id: int
    name: str
    category: AIAppCategory
    description: str
    camera_slot: Optional[int] = None  # Which camera slot (1-4) if applicable
    
    def __str__(self):
        return self.name
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category.value,
            'description': self.description,
            'camera_slot': self.camera_slot
        }


# All available AI applications
AI_APPS: Dict[int, AIApp] = {
    # AI-VMD (Video Motion Detection)
    272: AIApp(
        id=272,
        name="AI-VMD Camera 1",
        category=AIAppCategory.VMD,
        description="AI Video Motion Detection for Camera 1",
        camera_slot=1
    ),
    528: AIApp(
        id=528,
        name="AI-VMD Camera 2",
        category=AIAppCategory.VMD,
        description="AI Video Motion Detection for Camera 2",
        camera_slot=2
    ),
    784: AIApp(
        id=784,
        name="AI-VMD Camera 3",
        category=AIAppCategory.VMD,
        description="AI Video Motion Detection for Camera 3",
        camera_slot=3
    ),
    1040: AIApp(
        id=1040,
        name="AI-VMD Camera 4",
        category=AIAppCategory.VMD,
        description="AI Video Motion Detection for Camera 4",
        camera_slot=4
    ),
    
    # AI-People Detection
    279: AIApp(
        id=279,
        name="AI-People Camera 1",
        category=AIAppCategory.PEOPLE,
        description="AI People Detection for Camera 1",
        camera_slot=1
    ),
    535: AIApp(
        id=535,
        name="AI-People Camera 2",
        category=AIAppCategory.PEOPLE,
        description="AI People Detection for Camera 2",
        camera_slot=2
    ),
    791: AIApp(
        id=791,
        name="AI-People Camera 3",
        category=AIAppCategory.PEOPLE,
        description="AI People Detection for Camera 3",
        camera_slot=3
    ),
    1047: AIApp(
        id=1047,
        name="AI-People Camera 4",
        category=AIAppCategory.PEOPLE,
        description="AI People Detection for Camera 4",
        camera_slot=4
    ),
    
    # AI People Counting
    285: AIApp(
        id=285,
        name="AI-VMD and AI People Counting",
        category=AIAppCategory.PEOPLE_COUNTING,
        description="AI-VMD and AI People Counting",
        camera_slot=1
    ),
    
    # AI-Face Detection
    278: AIApp(
        id=278,
        name="AI-Face",
        category=AIAppCategory.FACE,
        description="AI Face Detection",
        camera_slot=None
    ),
    
    # AI-Vehicle Detection
    280: AIApp(
        id=280,
        name="AI-Vehicle Camera 1",
        category=AIAppCategory.VEHICLE,
        description="AI Vehicle Detection for Camera 1",
        camera_slot=1
    ),
    536: AIApp(
        id=536,
        name="AI-Vehicle Camera 2",
        category=AIAppCategory.VEHICLE,
        description="AI Vehicle Detection for Camera 2",
        camera_slot=2
    ),
    792: AIApp(
        id=792,
        name="AI-Vehicle Camera 3",
        category=AIAppCategory.VEHICLE,
        description="AI Vehicle Detection for Camera 3",
        camera_slot=3
    ),
    1048: AIApp(
        id=1048,
        name="AI-Vehicle Camera 4",
        category=AIAppCategory.VEHICLE,
        description="AI Vehicle Detection for Camera 4",
        camera_slot=4
    ),
    
    # Vaxtor License Plate Recognition
    8467: AIApp(
        id=8467,
        name="Vaxtor LPR",
        category=AIAppCategory.LPR,
        description="Vaxtor License Plate Recognition (GENESIS or MMC)",
        camera_slot=None
    ),
}


# Grouped by category for UI display
AI_APPS_BY_CATEGORY: Dict[AIAppCategory, List[AIApp]] = {
    AIAppCategory.VMD: [AI_APPS[id] for id in [272, 528, 784, 1040]],
    AIAppCategory.PEOPLE: [AI_APPS[id] for id in [279, 535, 791, 1047]],
    AIAppCategory.PEOPLE_COUNTING: [AI_APPS[285]],
    AIAppCategory.FACE: [AI_APPS[278]],
    AIAppCategory.VEHICLE: [AI_APPS[id] for id in [280, 536, 792, 1048]],
    AIAppCategory.LPR: [AI_APPS[8467]],
}


# Default AI apps (all VMD cameras)
DEFAULT_AI_APPS = [272, 528, 784, 1040]


def get_ai_app(app_id: int) -> Optional[AIApp]:
    """Get AI app by ID"""
    return AI_APPS.get(app_id)


def get_ai_app_name(app_id: int) -> str:
    """Get human-readable name for AI app"""
    app = AI_APPS.get(app_id)
    return app.name if app else f"Unknown AI App ({app_id})"


def get_all_ai_apps() -> List[AIApp]:
    """Get all AI apps as a list"""
    return list(AI_APPS.values())


def get_ai_apps_by_category(category: AIAppCategory) -> List[AIApp]:
    """Get AI apps for a specific category"""
    return AI_APPS_BY_CATEGORY.get(category, [])


def get_ai_apps_dict() -> Dict[str, List[dict]]:
    """Get AI apps grouped by category for API/UI"""
    return {
        category.value: [app.to_dict() for app in apps]
        for category, apps in AI_APPS_BY_CATEGORY.items()
    }
