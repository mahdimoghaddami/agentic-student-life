from .base import Agent
from ..prompts import COACH
class Coach(Agent):
    def __init__(self,model,tools,config):
        super().__init__('single' if config.mode=='single' else 'coach',COACH,model,tools,config)
