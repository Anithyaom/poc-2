from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.core.auth import current_user_sub
from src.course.models import Course
from src.course.schemas import CourseCreate, CourseDetail, CourseRead, LabSummary
from src.lab.models import Lab
from src.lab.schemas import LabCreate, LabRead
from src.lab.service import derive_title, latest_plan, read_lab

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[CourseRead])
async def list_courses() -> list[Course]:
    return await Course.filter(owner_sub=current_user_sub()).order_by("-created_at")


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(payload: CourseCreate) -> Course:
    return await Course.create(
        title=payload.title,
        subject=payload.subject,
        owner_sub=current_user_sub(),
    )


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(course_id: UUID) -> CourseDetail:
    course = await Course.get_or_none(id=course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    labs = await Lab.filter(course_id=course_id).order_by("-created_at")
    summaries = []
    for lab in labs:
        plan = await latest_plan(lab.id)
        summaries.append(
            LabSummary(
                id=lab.id,
                title=derive_title(lab.description, plan.plan_json if plan else None),
                audience=lab.audience,
                status=lab.status,
                created_at=lab.created_at,
            )
        )

    return CourseDetail(
        id=course.id,
        title=course.title,
        subject=course.subject,
        created_at=course.created_at,
        labs=summaries,
    )


@router.post("/{course_id}/labs", response_model=LabRead, status_code=status.HTTP_201_CREATED)
async def create_lab(course_id: UUID, payload: LabCreate) -> LabRead:
    course = await Course.get_or_none(id=course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lab = await Lab.create(
        course_id=course_id,
        description=payload.description,
        audience=payload.audience,
    )
    return await read_lab(lab)
