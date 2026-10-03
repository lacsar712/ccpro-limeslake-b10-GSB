from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Plant, Pond
from app.services.rules import RuleError, assert_can_set_pond_status

bp = Blueprint("ponds", __name__, url_prefix="/ponds")

STATUS_LABELS = {
    Pond.STATUS_FILLING: "注水中",
    Pond.STATUS_SLAKING: "熟化中",
    Pond.STATUS_DRAWN: "已出灰",
}


def admin_required(view):
    """更名台仅限管理员；操作工一律挡下。"""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            flash("仅管理员可使用池号更名台，操作工无权更名", "error")
            return redirect(url_for("board.floor_plan"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/rename")
@admin_required
def rename_ponds():
    ponds = Pond.query.join(Plant).order_by(Plant.name, Pond.code).all()
    return render_template(
        "ponds/rename.html",
        ponds=ponds,
        status_labels=STATUS_LABELS,
    )


@bp.route("/<int:pond_id>/rename", methods=["POST"])
@admin_required
def rename_pond(pond_id: int):
    pond = db.session.get(Pond, pond_id) or abort(404)
    new_code = (request.form.get("new_code") or "").strip()
    plant_name = pond.plant.name

    if not new_code:
        flash("更名失败：新池号不能为空", "error")
        return redirect(url_for("ponds.rename_ponds"))

    if new_code == pond.code:
        flash(f"新池号与原池号相同（{pond.code}），无需更名", "ok")
        return redirect(url_for("ponds.rename_ponds"))

    # 预检：同厂池号不得撞车。唯一约束在提交时再兜底一次并发同名。
    dup = Pond.query.filter(
        Pond.plant_id == pond.plant_id,
        Pond.code == new_code,
        Pond.id != pond.id,
    ).first()
    if dup:
        flash(
            f"更名失败：厂区「{plant_name}」已存在池号 {new_code}，同厂池号不得重复，原池号 {pond.code} 未改动",
            "error",
        )
        return redirect(url_for("ponds.rename_ponds"))

    old_code = pond.code
    pond.code = new_code  # 只改池号；状态、容量、备注等一律不碰
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            f"更名失败：厂区「{plant_name}」的池号 {new_code} 刚被他人占用，本次更名未生效，请刷新后重试",
            "error",
        )
        return redirect(url_for("ponds.rename_ponds"))

    flash(f"池号已由 {old_code} 更名为 {new_code}，池状态保持不变", "ok")
    return redirect(url_for("ponds.rename_ponds"))


@bp.route("/")
@login_required
def list_ponds():
    ponds = Pond.query.join(Plant).order_by(Plant.name, Pond.code).all()
    plants = Plant.query.order_by(Plant.name).all()
    return render_template(
        "ponds/list.html",
        ponds=ponds,
        plants=plants,
        status_labels=STATUS_LABELS,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_pond():
    plants = Plant.query.order_by(Plant.name).all()
    if request.method == "POST":
        plant_id = int(request.form["plant_id"])
        code = (request.form.get("code") or "").strip()
        status = request.form.get("status") or Pond.STATUS_FILLING
        capacity = float(request.form.get("capacity_m3") or 0)
        notes = (request.form.get("notes") or "").strip()
        if Pond.query.filter_by(plant_id=plant_id, code=code).first():
            flash("同一厂区内池编号必须唯一", "error")
        else:
            pond = Pond(
                plant_id=plant_id,
                code=code,
                status=status if status != Pond.STATUS_DRAWN else Pond.STATUS_FILLING,
                capacity_m3=capacity,
                notes=notes,
            )
            if status == Pond.STATUS_DRAWN:
                flash("新建池不能直接设为已出灰，已改为注水中", "error")
            db.session.add(pond)
            db.session.commit()
            flash("熟化池已创建", "ok")
            return redirect(url_for("board.floor_plan", plant_id=plant_id))
    return render_template(
        "ponds/form.html",
        pond=None,
        plants=plants,
        status_labels=STATUS_LABELS,
    )


@bp.route("/<int:pond_id>/edit", methods=["GET", "POST"])
@login_required
def edit_pond(pond_id: int):
    pond = Pond.query.get_or_404(pond_id)
    plants = Plant.query.order_by(Plant.name).all()
    if request.method == "POST":
        plant_id = int(request.form["plant_id"])
        code = (request.form.get("code") or "").strip()
        status = request.form.get("status") or pond.status
        capacity = float(request.form.get("capacity_m3") or 0)
        notes = (request.form.get("notes") or "").strip()
        # 操作工禁止更名：借编辑页改池号同样挡下，其他字段仍可维护。
        if current_user.role != "admin" and code != pond.code:
            flash("操作工无权更改池号，池号保持原值", "error")
            code = pond.code
        dup = Pond.query.filter(
            Pond.plant_id == plant_id,
            Pond.code == code,
            Pond.id != pond.id,
        ).first()
        if dup:
            flash("同一厂区内池编号必须唯一", "error")
        else:
            try:
                assert_can_set_pond_status(pond, status)
                pond.plant_id = plant_id
                pond.code = code
                pond.status = status
                pond.capacity_m3 = capacity
                pond.notes = notes
                db.session.commit()
                flash("熟化池已更新", "ok")
                return redirect(url_for("board.floor_plan", plant_id=plant_id, pond=pond.id))
            except RuleError as exc:
                flash(str(exc), "error")
    return render_template(
        "ponds/form.html",
        pond=pond,
        plants=plants,
        status_labels=STATUS_LABELS,
    )
