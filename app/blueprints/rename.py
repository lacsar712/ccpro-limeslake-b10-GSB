"""池号更名台：管理员专页改池号。

只改池号（Pond.code），不动池态等其他字段；
同厂池号唯一由应用校验 + 数据库唯一约束双重保证，
并发撞号时后提交的一笔整体回滚并用中文挡下。
"""

import functools

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Plant, Pond

bp = Blueprint("rename", __name__, url_prefix="/rename")

STATUS_LABELS = {
    Pond.STATUS_FILLING: "注水中",
    Pond.STATUS_SLAKING: "熟化中",
    Pond.STATUS_DRAWN: "已出灰",
}


def admin_required(view):
    """仅管理员可用；操作工一律中文挡回平面图。"""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            flash("仅管理员可执行池号更名", "error")
            return redirect(url_for("board.floor_plan"))
        return view(*args, **kwargs)

    return wrapper


@bp.route("/")
@login_required
@admin_required
def console():
    ponds = Pond.query.join(Plant).order_by(Plant.name, Pond.code).all()
    return render_template(
        "rename/console.html",
        ponds=ponds,
        status_labels=STATUS_LABELS,
    )


@bp.route("/<int:pond_id>", methods=["POST"])
@login_required
@admin_required
def rename_pond(pond_id: int):
    pond = Pond.query.get_or_404(pond_id)
    new_code = (request.form.get("new_code") or "").strip()

    if not new_code:
        flash("新池号不能为空", "error")
        return redirect(url_for("rename.console"))
    if len(new_code) > 40:
        flash("新池号最长 40 个字符", "error")
        return redirect(url_for("rename.console"))
    if new_code == pond.code:
        flash("新池号与原池号相同，未做修改", "error")
        return redirect(url_for("rename.console"))

    conflict = Pond.query.filter(
        Pond.plant_id == pond.plant_id,
        Pond.code == new_code,
        Pond.id != pond.id,
    ).first()
    if conflict:
        flash(f"更名失败：池号 {new_code} 在「{pond.plant.name}」已被占用", "error")
        return redirect(url_for("rename.console"))

    old_code = pond.code
    # 只改池号：池态、容量、备注等字段一律不动
    pond.code = new_code
    try:
        db.session.commit()
    except IntegrityError:
        # 并发场景：另一管理员已抢先占用该池号。
        # 依赖 uq_pond_code_per_plant 唯一约束兜底，整笔回滚，不留半改。
        db.session.rollback()
        flash(
            f"更名失败：池号 {new_code} 在「{pond.plant.name}」已被占用，本次更名未生效",
            "error",
        )
        return redirect(url_for("rename.console"))

    flash(f"池号已由 {old_code} 更名为 {new_code}", "ok")
    return redirect(url_for("rename.console"))
