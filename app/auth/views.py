from flask import render_template, redirect, url_for, flash, request, current_app, \
            session, abort, g, make_response
from . import auth
from .forms import LoginForm, RegistrationForm, EditUserProfileForm, AvatarForm, PostForm
from ..models import User, Post
from flask_login import login_user, logout_user, login_required, current_user
from flask_principal import Principal, Identity, AnonymousIdentity, identity_changed
from .permissions import admin_permission, editor_permission, reader_permission
from werkzeug import secure_filename


@auth.before_app_request
def before_request():
    '''更新用户访问时间'''
    if current_user.is_authenticated:
        current_user.ping()


@auth.route('/')
def index():
    return render_template('auth/index.html', current_user=current_user, title='管理首页')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.objects.get_or_404(username=form.username.data)
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)

            # Tell Flask-Principal the identity changed
            identity_changed.send(current_app._get_current_object(),
                                    identity=Identity(user.username))
                                    # identity=Identity(str(user.id)))

            if current_user.is_authenticated:
                flash('%s login successfully.' % (current_user.username))
            next = request.args.get('next')
            return redirect(next or url_for('auth.index'))
        flash('Invalid username or password.')
    return render_template('auth/login.html', form=form, current_user=current_user, title='用户登录')


@auth.route('/logout')
@login_required
def logout():
    logout_user()

    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())

    flash('You have been logged out.')
    return redirect(url_for('auth.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data)
        user.password = form.password.data
        user.role = form.role.data
        user.save()
        flash('注册成功，现在可以登录了!')
    return render_template('auth/register.html', form=form, title='用户注册')


@auth.route('/admin')
@login_required
# @reader_permission.require()    # user.role='reader',顺利访问
@admin_permission.require(http_exception=401)    # user.role='reader', flask_principal.PermissionDenied
def admin():
    # if not g.identity.can(admin_permission):
    #     abort(401)
    return render_template('auth/test_admin.html')


@auth.route('/profile/<username>')
@login_required
def user_profile(username):
    user = User.objects.get_or_404(username=username)
    return render_template('auth/user_profile.html', user=user)


@auth.route('/edit-profile/<username>', methods=['GET', 'POST'])
@login_required
def edit_profile(username):
    user = User.objects.get_or_404(username=username)
    form = EditUserProfileForm(user=user)
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.about_me = form.about_me.data
        user.save()
        flash('修改个人资料成功！')
        return redirect(url_for('auth.user_profile'))
    form.username.data = user.username
    form.email.data = user.email
    form.about_me.data = user.about_me
    return render_template('auth/edit_profile.html', form=form, user=user, title='用户资料设置')

    # 在shell下操作上传图像ok
    # >>> u = User.objects.get(username='novblog')
    # >>> im = open('/home/eliefly/Pictures/1.jpg', 'rb')
    # >>> u.avatar.put(im, content_type='image/jpeg')
    # >>> u.avatar
    # <ImageGridFsProxy: 584837afcaffbc1656e0e25d>
    # >>> u.save()

@auth.route('/static/avatar/<username>')
def avatar(username):
    '''为显示头像，新增头像的 URL，嵌入到 img tag 的 src 属性中'''
    user = User.objects.get_or_404(username=username)
    img = user.avatar.read()
    response = make_response(img)
    response.headers['Content-Type'] = 'image/jpeg'
    return response


@auth.route('/avatar/<username>', methods=('GET', 'POST'))
@login_required
def upload(username):
    user = User.objects.get_or_404(username=username)
    form = AvatarForm()
    if form.validate_on_submit():
        filename = secure_filename(form.avatar.data.filename)
        if len(filename) > 0:   # there is file is selected.
            ext = filename.split('.')[1]
            if ext not in current_app.config['AVATER_FORMAT']:
                flash("请上传'jpg', 'png', 'jpeg', 'bmp'格式图像！")
            else:
                avatar_data = form.avatar.data
                if user.avatar is not None:
                    user.avatar.replace(avatar_data, content_type='image/jpeg')
                else:
                    user.avatar.put(avatar_data, content_type='image/jpeg')
                user.save()
                flash('变更头像成功！')
                return redirect(url_for('auth.edit_profile', username=user.username))
    return render_template('auth/upload.html', form=form, user=user, title='上传头像')


@auth.route('/newpost/<username>', methods=['GET', 'POST'])
@login_required
@editor_permission.require(http_exception=401)
def new_post(username):
    user = User.objects.get_or_404(username=username)
    form = PostForm()
    tags = Post.objects().distinct('tags')
    categories = Post.objects().distinct('category')
    if form.validate_on_submit():
        post = Post(content=form.content.data)
        post.author = user
        post.title = form.title.data
        # post.status = form.status.data
        post.category = form.category.data.strip() if form.category.data.strip() else None
        post.tags = [tag.strip() for tag in form.tags.data.split(',')] if form.tags.data else None        

        if request.form.get('publish'):
            post.status = '发布'
            post.save()
            flash('文章发布成功！')
        elif request.form.get('draft'):
            post.status = '草稿'
            post.save()
            flash('文章已保存到为草稿！')
        return redirect(url_for('auth.index'))
    return render_template('auth/new_post.html', form=form, user=user, tags=tags, categories=categories, title='新建博客')


@auth.route('/managepost/<username>', methods=['GET', 'POST'])
@login_required
@editor_permission.require(http_exception=401)
def manage_post(username):
    user = User.objects.get_or_404(username=username)
    page = request.args.get('page', 1, type=int)
    pagination = Post.objects(author=user, status='发布').order_by('-publish_time').paginate(
                page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items

    # posts = Post.objects(author=user, status='发布').order_by('-publish_time')

    return render_template('auth/manage_post.html', posts=posts, user=user, pagination=pagination, endpoint='auth.manage_post', 
                            title='我的随笔', head=('%s的随笔' % username))


@auth.route('/draft/<username>', methods=['GET', 'POST'])
@login_required
@editor_permission.require(http_exception=401)
def draft_post(username):
    user = User.objects.get_or_404(username=username)
    page = request.args.get('page', 1, type=int)
    pagination = Post.objects(author=user, status='草稿').order_by('-publish_time').paginate(
                page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items

    # posts = Post.objects(author=user, status='草稿').order_by('-publish_time')
    return render_template('auth/manage_post.html', posts=posts, user=user, pagination=pagination, endpoint='auth.draft_post', 
                            title='草稿箱', head=('%s的草稿箱' % username))


@auth.route('/managepost/delete/<postid>', methods=['GET', 'DELETE'])
@login_required
@editor_permission.require(http_exception=401)
def delete_post(postid):
    post = Post.objects(id=postid).first()
    username = post.author.username
    post.delete()

    flash('删除成功！')

    # if request.args.get('ajax'):
    #     return 'success'
    if post.status == '草稿':
        return redirect(url_for('auth.draft_post', username=username))
    elif post.status == '发布':
        return redirect(url_for('auth.manage_post', username=username))

@auth.route('/managepost/edit/<postid>', methods=['GET', 'POST'])
@login_required
@editor_permission.require(http_exception=401)
def edit_post(postid):
    post = Post.objects(id=postid).first()
    if current_user != post.author:
        abort(403)
    form = PostForm()
    tags = Post.objects().distinct('tags')
    categories = Post.objects().distinct('category')
    if form.validate_on_submit():
        post.content = form.content.data
        post.title = form.title.data
        # post.status = form.status.data
        post.category = form.category.data.strip() if form.category.data.strip() else None
        post.tags = [tag.strip() for tag in form.tags.data.split(',')] if form.tags.data else None 
        if request.form.get('publish'):
            post.status = '发布'
            post.save()
            flash('文章发布成功！')
            return redirect(url_for('auth.manage_post', username=current_user.username))
        elif request.form.get('draft'):
            post.status = '草稿'
            post.save()
            flash('文章已保存到为草稿！')
            return redirect(url_for('auth.draft_post', username=current_user.username))
    form.title.data = post.title
    form.content.data = post.content
    form.tags.data = ','.join(post.tags)
    form.category.data = post.category    
    return render_template('auth/new_post.html', form=form, tags=tags, categories=categories, title='编辑文章"%s"' % post.title)

