from twisted.internet import reactor
from twisted.web.server import Site, resource
from twisted.web.static import File
from twisted.python import log
import cgi, sys, os, subprocess, shutil
import pymongo
import jinja
from bson import ObjectId
import datetime, time
import moss

log.startLogging(sys.stdout)

import re, StringIO, random, hashlib, base64

class Templater:

    def __init__(self):
        self.env = jinja.Environment(loader=jinja.FileSystemLoader("templates"))

    def render(self, template_id, vars={}):
        return str(self.env.get_template(template_id).render(vars))

templator = Templater()

conn = pymongo.MongoClient("localhost", 27017)
db = conn.pc3

def randomHash():
    return hashlib.md5("%s"%random.getrandbits(128)).hexdigest()

# Note: random_hash_fn MUST be constant-length
def findCollision(random_hash_fn=randomHash, max_d_size=100000000):
    depth = 1
    for depth in range(len(random_hash_fn())):
        d = set()
        n = 0
        while 1:
            n += 1
            h = random_hash_fn()[:depth]
            if h not in d:
                d.add(h)
            else:
                print "Collision at depth=%i, n=%i, h=%s"%(depth, n, h)
                break
            if n > max_d_size:
                print "depth=%i No collision found after %i iterations."%(depth,n)
                break

def buildDirectories():
    bak_dir = "bak-%s"%time.time()
    os.mkdir(bak_dir)
    if os.path.exists("data/"):
        newdir = "%s/data"
        os.mkdir(newdir)
        shutil.move("data", newdir)
    os.mkdir("data")
    if os.path.exists("root/"):
        newdir = "%s/root"%bak_dir
        os.mkdir(newdir)
        shutil.move("root", newdir)
    os.mkdir("root")
    pass

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
                         directory, time, runtime):
        self.db.results.insert({"username": username, "problem": problem_id,
                                "code_filepath": filepath, "success": result[0],
                                "compiler_output": result[1],
                                "output": result[2], "time": time,
                                "runtime": runtime,
                                "program_directory": directory})
        pass

    def getProgramOutput(self, username=None, problem_id=None, result=None, directory=None):
        search = {}
        if username:
            search["username"] = username
        if problem_id:
            search["problem"] = problem_id
        if result:
            search["success"] = result
        if directory:
            search["program_directory"] = directory
        l = list(self.db.results.find(search))
        for p in l:
            p["time"] = datetime.datetime.fromtimestamp(p["time"]).strftime("%Y-%m-%d")
            pass
        return l

    def getUserCookie(self, username=None, cookie=None):
        search = {}
        if username:
            search["username"] = username
        if cookie:
            search["cookie"] = cookie
        return self.db.cookies.find(search)

    def setResultMatched(self, directory, matched):
        self.db.results.update({"program_directory": directory}, {"$set": {"matched": matched}})
        pass

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

def seedDatabase():
    conn.copy_database("pc3", "pc3_%i"%int(time.time()))
    conn.drop_database("pc3")
    db = conn.pc3
    pw = base64.b64encode(randomHash())[0:10].replace("/", "S")
    User("root", "admin", pw)
    print "Set username/password to root/%s"%pw
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
    compiler_output = ""
    output = ""
    did_run = True
    runtime = 0.0
    try:
        CHUSER = []#["sudo","-u","pc3-user"]
        compiler_output += subprocess.check_output(["javac", "-C", "%s.java"%filename], stderr=subprocess.STDOUT)
        compiler_output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)

        start_time = time.time()
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
        end_time = time.time()
        runtime = end_time-start_time
    except subprocess.CalledProcessError as e:
        compiler_output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime)

import StringIO, json

def run_program(directory, username, problem_id, filename):
    #i = StringIO.StringIO("fdsa")

    if False: # If we ever want to consider a chroot, this code is a start.
        problem = dbi.getProblem(problem_id)
        if not problem:
            print "There is no such problem '%s'!"%problem_id
            return False

        #open("/tmp/pc3", "w").write(json.dumps({"directory": directory, "lang": "JavaWithRunner", "filename": filename, "runner_name": problem["runner_name"]}))
        open("/tmp/pc3", "w").write(directory)
        shutil.copytree("root/%s"%directory, "chroot/tmp/%s"%directory)
        shutil.copyfile("data/runners/%s.java"%problem["runner_name"], "./chroot/tmp/%s/%s.java"%(directory,problem["runner_name"]))
        open("chroot/tmp/%s/pc3-config"%directory, "w").write(json.dumps({"directory": directory, "lang": "JavaWithRunner", "filename": filename, "runner_name": problem["runner_name"]}))
        #os.chdir("chroot/tmp/%s"%directory)
        retval = subprocess.check_output("python run-program.py", stdin=open("/tmp/pc3"), stderr=open("err.log", "w"), shell=True)
        #os.chdir("../../..")
        return tuple(json.loads(retval))

    problem = dbi.getProblem(problem_id)
    if not problem:
        print "There is no such problem '%s'!"%problem_id
        return False

    # Enter the problem directory.
    filename, extension = (filename.split(".")[0], filename.split(".")[1])
    os.chdir("root")
    os.chdir(directory)
    print "Entering directory %s..."%directory

    output = ""
    result = (False, "")
    if problem["type"] == "JavaWithRunner":
        # Copy in the runner, and run the program.
        shutil.copyfile("../../data/%s/%s.java"%(problem["directory"],problem["runner_name"]), "./%s.java"%problem["runner_name"])
        result = handle_JavaWithRunner(filename, problem["runner_name"])
        output = result[1]

    os.chdir("../..")
    dbi.addProgramOutput(username, problem_id, "%s/%s.java"%(directory,filename), result, directory, time.time(), result[3])
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
        elif name == "cheating":
            return PlagiarismView()
        if check_auth_type(request) == "admin":
            return AdminView()
        if check_auth_type(request) == "student":
            return StudentView()
        return self

    def render_GET(self, request):
        if "logout" in request.args and check_auth_type(request) != "":
            request.addCookie("pc3-user", "")
            request.addCookie("pc3-cookie", "")
            u = User(check_auth_username(request))
            u.logout()
            return templator.render("index.html")
            return "<html><body>You're logged out.</body></html>"
        return templator.render("index.html", {"users": dbi.getUserList(), "problems": dbi.getProblemList(), "usertype": check_auth_type(request)})

# Check the type of user that is logged in
def check_auth_type(request):
    # Check for (student) authentication
    if not request.getCookie("pc3-user"):
        return ""
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

def getFileFromRequest(request, field_name="upl_file", contents=None):
    headers = request.getAllHeaders()

    if not contents:
        header_content = request.content.read()
    else:
        header_content = contents
    match = re.search(r'name="%s";\s*filename="([^\"]*)"'%field_name, header_content)
    if match:
        file_contents = match.groups()[0]
    else:
        return None

    return (file_contents, request.args[field_name][0])

class LoginView(resource.Resource):
    def render_POST(self, request):
        if "username" in request.args and "password" in request.args:
            u = User(request.args["username"][0])
            cookie = u.login(request.args["password"][0])
            if cookie:
                request.addCookie("pc3-user", request.args["username"][0])
                request.addCookie("pc3-auth", cookie)
                return templator.render("index.html", {"usertype": u.getType()})
                return "Welcome!"
            else:
                return templator.render("index.html")
                return "Too bad."
        return "Ummm... How did you get here?"

class AuthorizationErrorView(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        return templator.render("failed-auth.html")

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

class ResultsView(resource.Resource):
    isLeaf = True
    def student(self, request, username):
        s = ""
        results = list(dbi.getProgramOutput(username=username))
        results_by_problem = {}
        for r in results:
            if r["problem"] not in results_by_problem:
                results_by_problem[r["problem"]] = [r]
            else:
                results_by_problem[r["problem"]].append(r)
        problems = {}
        for p_key,p in results_by_problem.items():
            problems[p_key] = dbi.getProblem(p_key)
        #print results_by_problem, problems
        return {"results": results_by_problem, "problems": problems}
        return templator.render("results.html", {"org": "student_by_problem",
                                                 "results": results_by_problem,
                                                 "problems": problems})
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

    def result(self, result_id):
        output = dbi.getProgramOutput(directory=result_id)[0]
        problem = dbi.getProblem(output["problem"])
        matched = True
        match = ""
        need_match = False
        if "match" in problem and output["success"]:
            matched = output["matched"]
            need_match = True

        if not output["success"]:
            outputs = output["compiler_output"] + output["output"]
        else:
            outputs = output["output"]
        outputs = outputs.replace("<", "&lt;")
        outputs = outputs.replace(">", "&gt;")
        outputs = outputs.replace("\n", "<br/>")
        return templator.render("read-output.html", {"program_output": outputs,
                                                     "success": output["success"],
                                                     "matched": matched,
                                                     "need_match": need_match,
                                                     "match": match,
                                                     "result": output})

    def render_GET(self, request):
        if "result_id" in request.args:
            return self.result(request.args["result_id"][0])
        if "source_id" in request.args:
            result = dbi.getProgramOutput(directory=request.args["source_id"][0])[0]
            fname = "root/%s"%result["code_filepath"]
            outputs = open(fname).read()
            outputs = outputs.replace("<", "&lt;")
            outputs = outputs.replace(">", "&gt;")
            return templator.render("view-source.html", {"result": result, "source_code": outputs})

        if check_auth_type(request) == "student":
            #return self.student(request, check_auth_username(request))
            v = {}
            v["org"] = "student_by_problem"
            v["student"] = self.student(request, check_auth_username(request))
            #print v
            return templator.render("results.html", v)
        v = {}
        v["org"] = "teacher_by_user"
        v["students"] = []
        for u in dbi.getUserList():
            s = self.student(request, u["username"])
            s["name"] = u["username"]
            v["students"].append(s)
        return templator.render("results.html", v)
        v = {}
        v["users"] = []
        for u in dbi.getUserList():
            d = {"username": u["username"], "results": []}
            for r in dbi.getProgramOutput(username=u["username"]):
                d["results"].append(r)
            v["users"].append(d)
        v["org"] = "teacher_by_user"
        return templator.render("results.html", v)

class PlagiarismView(resource.Resource):
    isLeaf = True

    # Ask the user how they want to dice the data
    def render_GET(self, request):
        if check_auth_type(request) != "admin":
            return templator.render("failed-auth.html")
        return templator.render("plagiarism-query.html", {"users": dbi.getUserList(), "problems": dbi.getProblemList()})

    def render_POST(self, request):
        # Go find a list of the successful results for this problem.
        results = dbi.getProgramOutput(problem_id=request.args["problem"][0],
                                       result=True)
        p = Plagiarism(request.args["problem"][0], False)
        for r in results:
            p.addFile("root/"+r["code_filepath"], dbi.getProblem(r["problem"])["name"], r["username"])
            pass
        url = p.getResult()
        return "<html><body>Look at <a href='%s'>%s</a></body></html>"%(url,url)

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
            return templator.render("admin-action.html", {"action": "adduser",
                                                          "username": username})
        elif action == "addproblem":
            name = request.args["name"][0]
            form_contents = request.content.read()
            runner_file = getFileFromRequest(request, contents=form_contents)
            match_file = getFileFromRequest(request, "upl_match_file", contents=form_contents)
            #print match_file
            directory = randomHash()
            os.mkdir("data/%s/"%directory)
            open("data/%s/%s"%(directory,runner_file[0]), "w").write(runner_file[1])
            problem = {"type": "JavaWithRunner", "name": name, "runner_name": runner_file[0].split(".")[0], "directory": directory}
            if match_file:
                open("data/%s/match"%directory, "w").write(match_file[1])
                problem["match"] = {"filename": "match"}
                pass
            db.problems.insert(problem)
            return templator.render("admin-action.html", {"action": addproblem,
                                                          "problem_name": name})

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

        filename, extension = re.search(r'filename="(\w*).(\w*)"', request.content.read()).groups()

        d = randomHash()
        os.mkdir("root/%s"%d)

        out = open("root/%s/%s.%s"%(d,filename,extension), "wb")
        out.write(request.args["upl_file"][0])
        out.close()

        problem_id = request.args["problem"][0]

        # Run it (or queue it for running, or whatever)
        print "%s.%s"%(filename,extension)
        result = run_program(d, username, problem_id, filename+"."+extension)
        if result[0]:
            output = result[2]
        else:
            output = result[1] + result[2]

        # Check to see if there was some sort of output we needed to match.
        problem = dbi.getProblem(problem_id)
        matched = True
        match = ""
        need_match = False
        if "match" in problem and result[0]:
            need_match = True
            match = open("data/%s/%s"%(problem["directory"],problem["match"]["filename"])).read()
            if output == match:
                matched = True
            else:
                matched = False
            dbi.setResultMatched(d, matched)
            pass

        output = output.replace("<", "&lt;")
        output = output.replace(">", "&gt;")
        output = output.replace("\n", "<br/>")
        return templator.render("read-output.html", {"program_output": output,
                                                     "success": result[0],
                                                     "matched": matched,
                                                     "need_match":need_match,
                                                     "match": match})

def main():
    root = Root()
    site = Site(root)
    reactor.listenTCP(8005, site)
    reactor.run()

def signal_hup(signum, frame):
    reactor.stop()
    sys.exit(0)
    pass

import signal
signal.signal(signal.SIGHUP, signal_hup)

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--reset-db", action="store_true")
parser.add_argument("--find-collision", action="store_true")

args = parser.parse_args()

if args.reset_db:
    seedDatabase()
    buildDirectories()
elif args.find_collision:
    findCollision()
else:
    main()
