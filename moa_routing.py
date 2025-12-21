"""
MOA: Model-Organism Architecture
Multi-AI organ routing with functional separation and veto authority
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class Organ(Enum):
    SENSES = "senses"        # Gemini - perception/ingestion
    BRAIN = "brain"          # GPT - reasoning/planning
    CONSCIENCE = "conscience"  # Claude - truth/ethics
    HANDS = "hands"          # Grok - execution

class TaskClass(Enum):
    OBSERVATION = "observation"
    STRATEGY = "strategy"
    VALIDATION = "validation"
    EXECUTION = "execution"
    BUYER_FACING = "buyer_facing"
    CHANGE_CONTROL = "change_control"

@dataclass
class TaskRouting:
    primary_organ: Organ
    required_validators: List[Organ]
    optional_organs: List[Organ]
    privacy_tier_override: Optional[int] = None

class MOARouter:
    """
    Model-Organism Architecture Router
    Routes tasks to appropriate AI organs with validation chains
    """
    
    def __init__(self):
        # Define routing rules per task class
        self.routing_rules = {
            TaskClass.OBSERVATION: TaskRouting(
                primary_organ=Organ.SENSES,
                required_validators=[],
                optional_organs=[Organ.BRAIN]
            ),
            TaskClass.STRATEGY: TaskRouting(
                primary_organ=Organ.BRAIN,
                required_validators=[Organ.CONSCIENCE],
                optional_organs=[]
            ),
            TaskClass.VALIDATION: TaskRouting(
                primary_organ=Organ.CONSCIENCE,
                required_validators=[],
                optional_organs=[]
            ),
            TaskClass.EXECUTION: TaskRouting(
                primary_organ=Organ.HANDS,
                required_validators=[Organ.CONSCIENCE],
                optional_organs=[Organ.BRAIN]
            ),
            TaskClass.BUYER_FACING: TaskRouting(
                primary_organ=Organ.BRAIN,
                required_validators=[Organ.CONSCIENCE],
                optional_organs=[],
                privacy_tier_override=2  # Never tier 0-1 for buyer content
            ),
            TaskClass.CHANGE_CONTROL: TaskRouting(
                primary_organ=Organ.BRAIN,
                required_validators=[Organ.CONSCIENCE],
                optional_organs=[]
            )
        }
        
        # Map organs to AI models
        self.organ_to_model = {
            Organ.SENSES: "gemini",
            Organ.BRAIN: "gpt",
            Organ.CONSCIENCE: "claude",
            Organ.HANDS: "grok"
        }
    
    def classify_task(self, message: str, context: Optional[str] = None) -> TaskClass:
        """
        Classify what type of task this is based on message content
        """
        message_lower = message.lower()
        
        # Buyer-facing detection
        if any(word in message_lower for word in ['buyer', 'customer', 'client', 'earnout', 'valuation']):
            return TaskClass.BUYER_FACING
        
        # Execution detection
        if any(word in message_lower for word in ['build', 'create', 'implement', 'deploy', 'execute', 'write code']):
            return TaskClass.EXECUTION
        
        # Strategy detection
        if any(word in message_lower for word in ['plan', 'strategy', 'should we', 'how to approach', 'what if']):
            return TaskClass.STRATEGY
        
        # Validation detection
        if any(word in message_lower for word in ['validate', 'check', 'verify', 'is this correct', 'review']):
            return TaskClass.VALIDATION
        
        # Observation detection
        if any(word in message_lower for word in ['what is', 'analyze', 'summarize', 'extract', 'find']):
            return TaskClass.OBSERVATION
        
        # Default to strategy for complex queries
        return TaskClass.STRATEGY
    
    def detect_mode(self, message: str) -> str:
        """
        Detect user's working mode: ideating, executing, validating
        """
        message_lower = message.lower()
        
        # Ideating mode
        ideate_keywords = ['what if', 'could we', 'should we', 'idea', 'brainstorm', 'thinking about']
        if any(kw in message_lower for kw in ideate_keywords):
            return "ideating"
        
        # Executing mode
        execute_keywords = ['build', 'create', 'make', 'implement', 'deploy', 'write', 'add', 'fix']
        if any(kw in message_lower for kw in execute_keywords):
            return "executing"
        
        # Validating mode
        validate_keywords = ['check', 'verify', 'validate', 'review', 'is this', 'correct']
        if any(kw in message_lower for kw in validate_keywords):
            return "validating"
        
        # Researching mode
        research_keywords = ['what', 'how', 'why', 'explain', 'find', 'search']
        if any(kw in message_lower for kw in research_keywords):
            return "researching"
        
        return "general"
    
    def get_routing(
        self, 
        message: str, 
        privacy_tier: int,
        context: Optional[str] = None
    ) -> Dict:
        """
        Get complete routing plan for a task
        Returns: {
            'task_class': TaskClass,
            'mode': str,
            'primary_ai': str,
            'validators': List[str],
            'privacy_tier': int
        }
        """
        # Classify the task
        task_class = self.classify_task(message, context)
        
        # Detect mode
        mode = self.detect_mode(message)
        
        # Get routing rule
        routing = self.routing_rules[task_class]
        
        # Privacy tier override if needed
        final_tier = routing.privacy_tier_override if routing.privacy_tier_override is not None else privacy_tier
        
        # Map organs to models
        primary_ai = self.organ_to_model[routing.primary_organ]
        validators = [self.organ_to_model[org] for org in routing.required_validators]
        
        # Tier 3 always goes to ollama (local)
        if final_tier == 3:
            primary_ai = "ollama"
            validators = []  # No external validators for secrets
        
        return {
            'task_class': task_class.value,
            'mode': mode,
            'primary_ai': primary_ai,
            'validators': validators,
            'privacy_tier': final_tier,
            'requires_conscience_check': Organ.CONSCIENCE in routing.required_validators
        }
    
    def should_validate_with_tt01(self, task_class: TaskClass) -> bool:
        """
        Determine if TT-01 validation is required for this task
        """
        # Always validate buyer-facing, strategy, and execution
        validation_required = [
            TaskClass.BUYER_FACING,
            TaskClass.STRATEGY,
            TaskClass.EXECUTION,
            TaskClass.CHANGE_CONTROL
        ]
        
        return task_class in validation_required


# Quick test
if __name__ == "__main__":
    router = MOARouter()
    
    # Test different message types
    test_messages = [
        ("What's the weather like?", 0),
        ("Build me a login system", 1),
        ("Should we acquire this company?", 2),
        ("My SSN is 123-45-6789", 3),
        ("Validate this buyer proposal", 2)
    ]
    
    for msg, tier in test_messages:
        routing = router.get_routing(msg, tier)
        print(f"\nMessage: {msg}")
        print(f"Routing: {routing}")
