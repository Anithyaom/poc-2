from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.simulation.models import Simulation
from src.simulation.schemas import SimulationRead

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.get("/{simulation_id}", response_model=SimulationRead)
async def get_simulation(simulation_id: UUID) -> Simulation:
    simulation = await Simulation.get_or_none(id=simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation
