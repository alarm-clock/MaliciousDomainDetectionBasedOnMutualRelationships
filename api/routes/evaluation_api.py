from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from domain_evaluation.EvaluationApp import EvaluationApp
from domain_evaluation.EvaluationObjects import EvaluationJob
from misc.MemMonitor import enough_memory

router = APIRouter()

class EvaluationRequest(BaseModel):
    domain: str
    timeout: int | None = None

@router.post("/evaluate")
async def evaluate(req: EvaluationRequest):

    if not enough_memory():
        raise HTTPException(status_code=503, detail="Server is temporary overloaded. Please, try again later.")

    app = EvaluationApp.get_instance()

    if app is None:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    job_id = app.evaluate_domain_async(req.domain, req.timeout)

    return {'job_id': job_id}


@router.get("/evaluate/{job_id}")
def evaluate_job(job_id: str):

    app = EvaluationApp.get_instance()
    if app is None:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    job = app.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=400, detail=f"No job with id {job_id}")

    if not job.is_finished:
        return {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state)}
    else:
        if job.state == EvaluationJob.EvaluationState.FINISHED:
            res = {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state)} | job.result.to_dict
        else:
            res = {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state), "description": job.error_description}
        return res