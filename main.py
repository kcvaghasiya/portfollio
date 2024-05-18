import os
from flask import Flask, abort, render_template, redirect, url_for, flash, send_file
from flask_bootstrap import Bootstrap5
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("app_secret_key")
ckeditor = CKEditor(app)
Bootstrap5(app)


# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


current_year = datetime.now().year

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my_portfolio.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLE
class PortfolioProjects(db.Model):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="projects")

    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    project_url: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(50))
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250))


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    # This will act like a list of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    projects = relationship("PortfolioProjects", back_populates="author")

# Create a User table for contact form

class Contact(db.Model):
    __tablename__ = "contact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100))
    subject: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String(1000))


# WTForm
class CreateProjectForm(FlaskForm):
    title = StringField("Project Title", validators=[DataRequired()])
    project_url = StringField("Project Url", validators=[DataRequired()])
    category = SelectField("Category", choices=["Python", "Wordpress"], validators=[DataRequired()])
    img_url = StringField("Project Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Project Content", validators=[DataRequired()])
    submit = SubmitField("Submit Project")


# Create a form to register new users
class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Me Up!")


# Create a form to login existing users
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Let Me In!")

# WTForm
class CreateContactForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    subject = StringField("Subject")
    message = CKEditorField("Message")
    submit = SubmitField("Submit")


with app.app_context():
    db.create_all()

# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function



@app.route("/new-project", methods=["GET", "POST"])
@admin_only
def add_new_project():
    form = CreateProjectForm()
    if form.validate_on_submit():
        new_post = PortfolioProjects(
            title=form.title.data,
            project_url=form.project_url.data,
            category=form.category.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("projects"))
    return render_template("add-project.html", form=form)

@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
@admin_only
def edit_project(project_id):
    project = db.get_or_404(PortfolioProjects, project_id)
    edit_form = CreateProjectForm(
        title=project.title,
        project_url=project.project_url,
        category=project.category,
        img_url=project.img_url,
        author=current_user,
        body=project.body
    )
    if edit_form.validate_on_submit():
        project.title = edit_form.title.data
        project.project_url = edit_form.project_url.data
        project.category = edit_form.category.data
        project.img_url = edit_form.img_url.data
        project.author = current_user
        project.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("projects", project_id=project.id))
    return render_template("add-project.html", form=edit_form, is_edit=True)

@app.route("/delete/<int:project_id>")
@admin_only
def delete_project(project_id):
    post_to_delete = db.get_or_404(PortfolioProjects, project_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('projects'))


# Register new users into the User database
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))



@app.route('/')
def home():
    return render_template("index.html", current_year=current_year, current_user=current_user)

@app.route('/resume')
def resume():
    return render_template("resume.html", current_year=current_year, current_user=current_user)

@app.route('/download')
def download():
    path = "CV-2024.pdf"
    return send_file(path, as_attachment=True)

@app.route('/projects')
def projects():
    result = db.session.execute(db.select(PortfolioProjects))
    # result = db.session.execute(db.select(PortfolioProjects).where(PortfolioProjects.category == "wordpress"))
    projects = result.scalars().all()
    return render_template("projects.html", current_year=current_year, all_project=projects, current_user=current_user)

@app.route("/project/<int:project_id>")
def show_single_project(project_id):
    requested_project = db.get_or_404(PortfolioProjects, project_id)
    return render_template("single-project.html", project=requested_project, current_user=current_user)



@app.route('/contact', methods=["GET", "POST"])
def contact():
    form = CreateContactForm()
    if form.validate_on_submit():
        new_contact = Contact(
            name=form.name.data,
            email=form.email.data,
            subject=form.subject.data,
            message=form.message.data
        )
        db.session.add(new_contact)
        db.session.commit()
        # create a message to send to the template
        message = "Your message has been submitted."
            # return redirect(url_for('contact'))
        return render_template("contact.html", form=form, current_year=current_year, current_user=current_user, message=message)
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash("Error in {}: {}".format(
                    getattr(form, field).label.text,
                    error
                ), 'error')
        return render_template("contact.html", form=form, current_year=current_year, current_user=current_user)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
