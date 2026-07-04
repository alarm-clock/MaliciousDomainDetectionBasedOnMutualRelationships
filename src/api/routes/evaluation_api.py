"""
File: evaluation_api.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 02.01.2026
Brief: File that contains API endpoints for asynchronous domain evaluation, including
    submitting evaluation jobs and obtaining their current state or result
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from domain_evaluation.EvaluationApp import EvaluationApp
from domain_evaluation.EvaluationObjects import EvaluationJob
from misc.MemMonitor import enough_memory

router = APIRouter()


class EvaluationRequest(BaseModel):
    """
    Class that represents request body for domain evaluation endpoint.
    """

    domain: str
    timeout: int | None = None


@router.post("/evaluate")
async def evaluate(req: EvaluationRequest):
    """
    Method that submits asynchronous evaluation job for given domain
    :param req: `EvaluationRequest` object containing domain to evaluate and optional timeout
    :return: `dict` dictionary containing identifier of created evaluation job
    :raises HTTPException: if server is overloaded or evaluation application instance is not available
    """

    # Reject request when available system memory is too low for safe evaluation processing.
    if not enough_memory():
        raise HTTPException(status_code=503, detail="Server is temporary overloaded. Please, try again later.")

    # Get shared evaluation application instance responsible for evaluation job scheduling.
    app = EvaluationApp.get_instance()

    # Evaluation application must be initialized before requests can be processed.
    if app is None:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # Submit asynchronous evaluation and obtain created job identifier.
    job_id = app.evaluate_domain_async(req.domain, req.timeout)

    return {'job_id': job_id}


@router.get("/evaluate/{job_id}")
def evaluate_job(job_id: str):
    """
    Method that returns current state or final result of evaluation job with given identifier
    :param job_id: `str` identifier of requested evaluation job
    :return: `dict` dictionary containing job state information or final evaluation result
    :raises HTTPException: if evaluation application instance is not available or job does not exist
    """

    # Get shared evaluation application instance used for job lookup.
    app = EvaluationApp.get_instance()
    if app is None:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # Try to locate evaluation job with given identifier.
    job = app.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=400, detail=f"No job with id {job_id}")

    # Return only state information while evaluation is still running.
    if not job.is_finished:
        return {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state)}
    else:
        # If job finished successfully, merge basic job info with evaluation result payload.
        if job.state == EvaluationJob.EvaluationState.FINISHED:
            res = {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state)} | job.result.to_dict

        # Otherwise return failure information together with error description.
        else:
            res = {'job_id': job_id, 'status_code': job.state.value, 'status_str': str(job.state), "description": job.error_description}

        return res