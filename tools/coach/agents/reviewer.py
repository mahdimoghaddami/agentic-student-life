from .base import Agent
from ..prompts import REVIEWER
class Reviewer(Agent):
    def __init__(self,model,tools,config):
        super().__init__('single' if config.mode=='single' else 'reviewer',REVIEWER,model,tools,config)
