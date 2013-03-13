from twisted.internet import reactor
from twisted.web.server import Site, resource
from twisted.web.static import File
from twisted.python import log
import cgi, sys, os, subprocess, shutil
import pymongo
import jinja
from bson import ObjectId
import time

log.startLogging(sys.stdout)

import re, StringIO, random, hashlib

class Templater:
    def __init__(self):
        self.env = jinja.Environment(loader=jinja.FileSystemLoader("templates"))

    def render(self, template_id, vars={}):
        return str(self.env.get_template(template_id).render(vars))

templator = Templater()

conn = pymongo.MongoClient("localhost", 27017)
db = conn.pc3

class DatabaseInterface:
    def __init__(self, db):
        self.db = db

    def getProblem(self, problem_name):
        return self.db.problems.find_one({"_id": ObjectId(problem_name)})

    def getProblemList(self):
        r = []
        for p in self.db.problems.find():
            p["_id"] = str(p["_id"])
            r.append(p)
        return r

    def getUserList(self):
        r = []
        for u in self.db.users.find():
            r.append(u)
        return r

    def addProgramOutput(self, username, problem_id, filepath, result,
                         directory, time):
        self.db.results.insert({"username": username, "problem": problem_id,
                                "code_filepath": filepath, "success": result[0],
                                "output": result[1], "time": time,
                                "program_directory": directory})
        pass

    def getProgramOutput(self, username=None, problem_id=None, result=None):
        search = {}
        if username:
            search["username"] = username
        if problem_id:
            search["problem"] = problem_id
        if result:
            search["success"] = result
        return self.db.results.find(search)

    def getUserCookie(self, username=None, cookie=None):
        search = {}
        if username:
            search["username"] = username
        if cookie:
            search["cookie"] = cookie
        return self.db.cookies.find(search)

dbi = DatabaseInterface(db)

class User:
    # If password and email are set, we create the user
    def __init__(self, username, type=None, password=None, email=None):
        self.username = username
        if password is not None:
            dbi.db.users.insert({"username": username, "password": password, "email": email, "type": type, "time_registered": time.time()})
        pass

    def getType(self):
        user = dbi.db.users.find_one({"username": self.username})
        return user["type"]

    # TRY to login with said password
    def login(self, password):
        user = dbi.db.users.find_one({"username": self.username})
        if user["password"] == password:
            cookie = hashlib.sha256(random.choice(user["password"])+random.choice(self.username)+password+str(time.time())+str(random.random())).hexdigest()
            dbi.db.cookies.insert({"username": self.username, "cookie": cookie})
            return cookie
        return None

    # Clear the defined cookie, or all cookies associated with the username.
    def logout(self, cookie=None):
        spec = {"username": self.username}
        if cookie:
            spec["cookie"] = cookie
        dbi.db.cookies.remove(spec)
        pass

class Plagiarism:
    def __init__(self, project_name, load_existing_files=True):
        self.project_name = project_name
        self.needs_update = True
        self.result_url = None
        self.moss = moss.Moss(353538543, "java")

        # Load all of the existing files
        if load_existing_files:
            pass

    def addFile(self, filename, project_name, user_name):
        self.moss.addFile(filename, project_name, user_name)
        self.needs_update = True

    def getResult(self):
        if self.needs_update:
            self.result_url = self.moss.upload()
        return self.result_url

def call_command(cmd):
    output = ""
    try:
        output += subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        output += e.output
        return (False, output)
    return (True, output)

def handle_JavaWithRunner(filename, runner_name):
    output = ""
    did_run = True
    try:
        output += subprocess.check_output(["javac", "-C", "%s.java"%filename], stderr=subprocess.STDOUT)
        output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        output += "FINISHED COMPILING...\n"
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, output)

import StringIO, json

def run_program(directory, username, problem_id, filename):
    #i = StringIO.StringIO("fdsa")

    if False:
        problem = dbi.getProblem(problem_id)
        if not problem:
            print "There is no such problem '%s'!"%problem_id
            return False

        open("/tmp/pc3", "w").write(json.dumps({"directory": directory, "lang": "JavaWithRunner", "filename": filename, "runner_name": problem["runner_name"]}))
        shutil.copytree("root/%s"%directory, "chroot/tmp/%s"%directory)
        shutil.copyfile("data/runners/%s.java"%problem["runner_name"], "./chroot/tmp/%s/%s.java"%(directory,problem["runner_name"]))
        retval = subprocess.check_output("python run-program.py", stdin=open("/tmp/pc3"), shell=True)
        return tuple(json.loads(retval))

    problem = dbi.getProblem(problem_id)
    if not problem:
        print "There is no such problem '%s'!"%problem_id
        return False

    # Go deal with some file system stuff...
    filename, extension = (filename.split(".")[0], filename.split(".")[1])
    os.chdir("root")
    os.chdir(directory)
    print "Entering directory %s..."%directory

    output = ""
    result = (False, "")
    if problem["type"] == "JavaWithRunner":
        shutil.copyfile("../../data/runners/%s.java"%problem["runner_name"], "./%s.java"%problem["runner_name"])
        result = handle_JavaWithRunner(filename, problem["runner_name"])
        output = result[1]

    os.chdir("../..")
    dbi.addProgramOutput(username, problem_id, "%s/%s.java"%(directory,filename), result, directory, time.time())
    return result

def run_program_old():
    # If it's a zip file, unzip it...
    output = ""
    if extension == "zip":
        #subprocess.check_output(["unzip", "%s.zip"%filename])
        output = call_command("unzip %s.zip"%filename)[1]

        # Compile all of the java files
        has_error = False
        for f in os.listdir("."):
            if os.path.splitext(f)[1] == ".java":
                retval = call_command("javac %s"%f)
                if not retval[0]:
                    output += retval[1]
                    has_error = True
                    break

        if not has_error:
            # Copy over the runner file
            shutil("../../data/runners/SongRunner.java", ".")
            output += call_command("java SongRunner.java")
            pass

        pass
    else:
        result = handle_JavaWithRunner()
        output += result[1]
        """
        output = ""
        try:
            output += subprocess.check_output(["javac", "SongRunner.java"], stderr=subprocess.STDOUT)
            output += subprocess.check_output(["java", "SongRunner"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            output += e.output
            """

    os.chdir("../..")
    return output

class Root(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        print "Name: %s"%name
        if name == "index.html" or name == "":
            return self
        elif name == "upload":
            return UploadView()
        elif name == "static":
            return File("./static")
        elif name == "admin":
            return AdminView()
        elif name == "students":
            return StudentView().getChild(request.prepath[1:], request)
        elif name == "login":
            return LoginView()
        elif name == "results":
            return ResultsView()
        return self

    def render_GET(self, request):
        #return open("./static/index.html").read()
        if "logout" in request.args and check_auth_type(request) != "":
            request.addCookie("pc3-user", "")
            request.addCookie("pc3-cookie", "")
            u = User(check_auth_username(request))
            u.logout()
            return "<html><body>You're logged out.</body></html>"
        #return "<html><body>Go to either <a href='students'>Students</a> or <a href='admin'>Administration</a> or <a href='?logout=1'>Logout</a></body></html>"
        return templator.render("index.html", {"users": dbi.getUserList(), "problems": dbi.getProblemList()})

# Check the type of user that is logged in
def check_auth_type(request):
    # Check for (student) authentication
    if not request.getCookie("pc3-user"):
        return ""
    #if request.getCookie("pc3-auth") in dbi.getUserCookie(username=request.getCookie("pc3-user")):
    cookies = dbi.getUserCookie(username=request.getCookie("pc3-user"))
    for c in cookies:
        if request.getCookie("pc3-auth") == c["cookie"]:
            u = User(request.getCookie("pc3-user"))
            return u.getType()
    return ""

def check_auth_username(request):
    if check_auth_type(request) == "":
        return None
    return request.getCookie("pc3-user")

def getFileFromRequest(request, field_name="upl_file"):
    headers = request.getAllHeaders()

    filename, extension = re.search(r'filename="(\w*).(\w*)"', request.content.read()).groups()

    return (filename+"."+extension, request.args[field_name][0])

class LoginView(resource.Resource):
    def render_POST(self, request):
        if "username" in request.args and "password" in request.args:
            u = User(request.args["username"][0])
            cookie = u.login(request.args["password"][0])
            if cookie:
                request.addCookie("pc3-user", request.args["username"][0])
                request.addCookie("pc3-auth", cookie)
                return templator.render("index.html")
                return "Welcome!"
            else:
                return "Too bad."
        return "Ummm... How did you get here?"

class AuthorizationErrorView(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        return templator.render("failed-auth.html")
        #return "<html><body>You don't have permission to access this page.<br/><form action='/login' method='POST'><input type='text' name='username'/><input type='password' name='password'/><input type='submit' name='submit'/></form></body></html>"#"<html><body>You aren't authorized.</body></html>"

class StudentView(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        if check_auth_type(request) != "student":
            return AuthorizationErrorView()
        return self

    def render_GET(self, request):
        if "action" in request.args:
            if request.args["action"][0] == "upload":
                templator.render("upload.html", {"users": dbi.getUserList(), "problems": dbi.getProblemList()})
                pass
        return templator.render("student-main.html", {"username": request.getCookie("pc3-user")})
        return "<html><body>Welcome, %s. You can:<br/><a href='/upload'>Submit something</a><br/>View my past submissions<br/></body></html>"%request.getCookie("pc3-user")

class ResultsView(resource.Resource):
    isLeaf = True
    def student(self, request, username):
        s = ""
        results = list(dbi.getProgramOutput(username=username))
        problems = {}
        for r in results:
            if r["problem"] not in problems:
                problems[r["problem"]] = [r]
            else:
                problems[r["problem"]].append(r)
        for p_key,p in problems.items():
            problem = dbi.getProblem(p_key)
            if "name" not in problem:
                continue # WTF?
            s += "<h1>%s</h1>"%problem["name"]
            s += "<ul>"
            for r in p:
                if r["success"]:
                    s += "<li>Success at %f</li>"%r.get("time",0.0)
                else:
                    s += "<li>Failure at %f</li>"%r.get("time",0.0)
                #s += "<li>%s</li>"%r
            s += "</ul>"
        return str("<html><body>Hello, %s. Here's your submissions:<br/>%s</body></html>"%(username, s))

    def render_GET(self, request):
        if check_auth_type(request) == "student":
            return self.student(request, check_auth_username(request))
        v = {}
        v["users"] = []
        for u in dbi.getUserList():
            d = {"username": u["username"], "results": []}
            for r in dbi.getProgramOutput(username=u["username"]):
                d["results"].append(r)
            v["users"].append(d)
        return templator.render("results.html", v)

class AdminView(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        if check_auth_type(request) != "admin":
            return templator.render("failed-auth.html")

        # Show the main admin page
        return templator.render("admin.html")
        return "<html><body>asdf</body></html>"

    def render_POST(self, request):
        if check_auth_type(request) != "admin":
            return templator.render("failed-auth.html")

        action = request.args.get("action", [""])[0]
        if action == "adduser":
            username = request.args["username"][0]
            password = request.args["password"][0]
            t = request.args["type"][0]
            db.users.insert({"username": username, "password": password, "type": t})
            return "<html><body>Successfully added user '%s'!<br/><a href=''>Go Back</a></body></html>"%username
        elif action == "addproblem":
            name = request.args["name"][0]
            runner_file = getFileFromRequest(request)
            open("data/runners/%s"%runner_file[0], "w").write(runner_file[1])
            db.problems.insert({"type": "JavaWithRunner", "name": name, "runner_name": runner_file[0].split(".")[0]})
            return "<html><body>Successfully added problem '%s'!<br/><a href=''>Go Back</a></body></html>"%name

        return "<html><body></body></html>"

class UploadView(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        if check_auth_type(request) != "student":
            return templator.render("failed-auth.html")
        return templator.render("upload.html", {"users": dbi.getUserList(), "problems": dbi.getProblemList()})

    def render_POST(self, request):
        if check_auth_type(request) != "student":
            return templator.render("failed-auth.html")
        username = check_auth_username(request)

        headers = request.getAllHeaders()
        #print request.args["upl_file"][0]
        #img = cgi.FieldStorage(fp=request.content, headers=headers, environ={"REQUEST": "POST", "CONTENT_TYPE": headers["content-type"]})
        #print headers, img, img.getlist("username")

        filename, extension = re.search(r'filename="(\w*).(\w*)"', request.content.read()).groups()

        d = random.random()
        d = hashlib.md5("%.10f"%d).hexdigest()
        os.mkdir("root/%s"%d)

        out = open("root/%s/%s.%s"%(d,filename,extension), "wb")
        out.write(request.args["upl_file"][0])
        out.close()

        problem_id = request.args["problem"][0]

        # Run it (or queue it for running, or whatever)
        #output = subprocess.check_output(["javac", "%s.java"%filename])
        #output += subprocess.check_output(["java", "%s"%filename])
        print "%s.%s"%(filename,extension)
        output = run_program(d, username, problem_id, filename+"."+extension)[1]

        output = output.replace("<", "&lt;")
        output = output.replace(">", "&gt;")
        output = output.replace("\n", "<br/>")
        return templator.render("read-output.html", {"program_output": output})

        # Comb output to make it nicer for HTML-formatted output
        output = output.replace("<", "&lt;")
        output = output.replace(">", "&gt;")
        output = output.replace("\n", "<br/>")
        output = "<html><body>%s<br/><a href=\"/\">Try again</a></body></html>"%output

        return output

root = Root()
site = Site(root)
reactor.listenTCP(8005, site)
reactor.run()
