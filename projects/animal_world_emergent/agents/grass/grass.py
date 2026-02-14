"""
Grass Growth Module
Provides interface for grass population dynamics and resource interaction with soil.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class GrassState:
    """Current state of a grass patch"""
    biomass: float  # total biomass (kg/ha)
    growth_rate: float  # current growth rate (kg/ha/day)
    health: float  # health index 0-1
    position: Tuple[int, int]  # grid position


class GrassModule:
    """
    Main grass module interface.
    Manages grass populations across a grid world.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize grass module with configuration.
        
        Args:
            config: Dictionary containing parameters like:
                - max_biomass: maximum biomass per cell (kg/ha)
                - growth_rate: base growth rate (per day)
                - recovery_rate: recovery after grazing
                - min_biomass: minimum viable biomass
                - nutrient_requirements: dict of nutrient->amount needed per biomass growth
        """
        self.config = config
        self.grass_patches: Dict[Tuple[int, int], GrassState] = {}
        
    def initialize_patch(self, position: Tuple[int, int], initial_biomass: float = None):
        """Create a new grass patch at given position."""
        if initial_biomass is None:
            initial_biomass = self.config.get('initial_biomass', 100.0)
        self.grass_patches[position] = GrassState(
            biomass=initial_biomass,
            growth_rate=self.config['growth_rate'],
            health=1.0,
            position=position
        )
    
    def update(self, dt: float, soil_resources: Dict[str, float]) -> Dict:
        """
        Update grass growth for all patches.
        
        Args:
            dt: time step in days
            soil_resources: dictionary of available soil resources at each position
                            Format: {(x,y): {'nutrients': {...}, 'water': float}}
        
        Returns:
            Dictionary with update statistics and resource consumption
        """
        consumption = {}
        for pos, patch in self.grass_patches.items():
            # Get local soil resources
            local_resources = soil_resources.get(pos, {'nutrients': {}, 'water': 0.0})
            
            # Calculate growth based on resource availability
            actual_growth = self._calculate_growth(patch, local_resources, dt)
            
            # Update biomass
            patch.biomass = min(
                patch.biomass + actual_growth,
                self.config['max_biomass']
            )
            
            # Record resource consumption
            consumption[pos] = self._calculate_consumption(patch, actual_growth, dt)
            
        return {
            'total_biomass': sum(p.biomass for p in self.grass_patches.values()),
            'consumption': consumption
        }
    
    def graze(self, position: Tuple[int, int], amount: float) -> float:
        """
        Simulate grazing at a position.
        
        Args:
            position: grid position
            amount: amount of grass to consume (kg/ha)
            
        Returns:
            Actual amount consumed (may be less if insufficient biomass)
        """
        if position not in self.grass_patches:
            return 0.0
            
        patch = self.grass_patches[position]
        actual_consumed = min(amount, patch.biomass)
        patch.biomass -= actual_consumed
        patch.health = max(0.0, patch.biomass / self.config['max_biomass'])
        return actual_consumed
    
    def get_state(self, position: Tuple[int, int]) -> Optional[GrassState]:
        """Get state of grass at specific position."""
        return self.grass_patches.get(position)
    
    def get_all_states(self) -> Dict[Tuple[int, int], GrassState]:
        """Get states of all grass patches."""
        return self.grass_patches.copy()
    
    def _calculate_growth(self, patch: GrassState, resources: Dict, dt: float) -> float:
        """Calculate actual growth based on resource limitations."""
        # Base exponential growth limited by carrying capacity
        max_biomass = self.config['max_biomass']
        growth_potential = patch.growth_rate * patch.biomass * (1 - patch.biomass / max_biomass) * dt
        
        # Resource limitation factor
        resource_factor = self._resource_limitation_factor(resources)
        
        # Health factor
        health_factor = patch.health
        
        return growth_potential * resource_factor * health_factor
    
    def _resource_limitation_factor(self, resources: Dict) -> float:
        """Calculate limitation factor from soil resources (0-1)."""
        nutrients = resources.get('nutrients', {})
        water = resources.get('water', 0.0)
        
        # Example: require N, P, K and water
        factors = []
        
        # Water limitation
        water_required = self.config.get('water_requirement', 50.0)  # mm
        factors.append(min(1.0, water / water_required) if water_required > 0 else 1.0)
        
        # Nutrient limitations
        for nutrient, required in self.config.get('nutrient_requirements', {}).items():
            available = nutrients.get(nutrient, 0.0)
            factors.append(min(1.0, available / required) if required > 0 else 1.0)
        
        # Overall limitation is minimum of all factors (Liebig's law)
        return min(factors) if factors else 1.0
    
    def _calculate_consumption(self, patch: GrassState, growth: float, dt: float) -> Dict:
        """Calculate resources consumed during growth."""
        nutrients_consumed = {}
        for nutrient, req in self.config.get('nutrient_requirements', {}).items():
            # nutrients per kg biomass growth
            nutrients_consumed[nutrient] = req * growth
        
        water_consumed = self.config.get('water_requirement', 50.0) * growth / patch.biomass if patch.biomass > 0 else 0
        
        return {
            'nutrients': nutrients_consumed,
            'water': water_consumed
        }


def create_default_config() -> Dict:
    """Create default configuration for grass module."""
    return {
        'max_biomass': 1000.0,  # kg/ha
        'growth_rate': 0.1,  # per day
        'initial_biomass': 100.0,
        'min_biomass': 10.0,
        'recovery_rate': 0.05,
        'nutrient_requirements': {
            'N': 0.02,  # kg N per kg biomass growth
            'P': 0.005,
            'K': 0.015
        },
        'water_requirement': 50.0  # mm water per kg biomass growth
    }