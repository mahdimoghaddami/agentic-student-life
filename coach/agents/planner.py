from .base import Agent
from ..prompts import PLANNER
class Planner(Agent):
    def __init__(self,model,tools,config):
        super().__init__('single' if config.mode=='single' else 'planner',PLANNER,model,tools,config)
