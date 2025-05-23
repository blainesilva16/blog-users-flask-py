import os, smtplib
from dotenv import load_dotenv
from datetime import date
from flask import session, Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import *

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

app.secret_key = b'3L_[4.Dbp1=;/m4'

# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First, check if the user is authenticated
        if not current_user.is_authenticated:
            flash("You need to log in as admin to access this page.")
            return redirect(url_for('login'))  # Redirect to the login page

        # Then, check if the current user's ID is 1 (the admin user)
        if current_user.id != 1:
            return render_template("unauthorized.html")

        # If both conditions are met, proceed with the route function
        return f(*args, **kwargs)
    return decorated_function

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Parent relationship to the comments
    comments = relationship("Comment", back_populates="parent_post")

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    # This will act like a list of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    # Parent relationship: "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")

# Create a table for the comments on the blog posts
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Child relationship:"users.id" The users refers to the tablename of the User class.
    # "comments" refers to the comments property in the User class.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    # Child Relationship to the BlogPosts
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    print(current_user)
    if 'username' in session:
        return render_template("index.html",
                               all_posts=posts,
                               current_user=current_user,
                               h1_text=session['username'])
    return render_template("index.html",
                           all_posts=posts,
                           current_user=current_user,
                           h1_text="The BS' Blog")

@app.route('/register', methods=["GET","POST"])
def register():
    form = RegisterForm()
    if 'username' in session:
        return redirect(url_for('home'))
    if form.validate_on_submit():
        check_user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if check_user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        new_user = User(
            name=form.name.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='pbkdf2', salt_length=8))
        db.session.add(new_user)
        db.session.commit()
        session['username'] = new_user.name
        flash('Logged in successfully.')
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html",form=form, current_user=current_user)

@app.route('/login', methods=["GET","POST"])
def login():
    form = LoginForm()
    if 'username' in session:
        return redirect(url_for('home'))
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user != None:
            if check_password_hash(user.password, form.password.data):
                flash('Logged in successfully.')
                session['username'] = user.name
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Password incorrect.")
                return redirect(url_for('login'))
        else:
            flash("User does not exist.")
            return redirect(url_for('login'))
    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    session.pop('username', None)
    logout_user()
    return redirect(url_for('home'))



@app.route("/post/<int:post_id>", methods=["GET","POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    # Only allow logged-in users to comment on posts
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, current_user=current_user,form=comment_form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("make-post.html", form=form, current_user=current_user)

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)

@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

@app.route("/about")
def about():
    if 'username' in session:
        return render_template("about.html", current_user=current_user)
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["GET","POST"])
def contact():
    # if request.method == "POST":
    #     # SET INFO HERE
    #     my_email = ""
    #     password = ""

    #     try:
    #         with smtplib.SMTP("", 587) as connection:
    #             connection.starttls()
    #             connection.login(user=my_email, password=password)
    #             connection.sendmail(
    #                 from_addr=my_email,
    #                 to_addrs="",
    #                 msg=f"Subject:New message!\n\nName: {request.form["name"]}\n"
    #                     f"Email: {request.form["email"]}\nPhone: {request.form["phone"]}\n"
    #                     f"Message: {request.form["message"]}")
    #     except:
    #         return render_template("contact.html", msg_sent=False)
    #     else:
    #         return render_template("contact.html", msg_sent=True)

    return render_template("contact.html",  msg_sent=False)

if __name__ == "__main__":
    app.run(debug=False)
