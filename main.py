from twisted.internet import reactor
from twisted.web.server import Site, resource
from twisted.web.static import File
from twisted.python import log
import cgi, sys, os, subprocess, shutil

log.startLogging(sys.stdout)

import re, StringIO, random, hashlib

def call_command(cmd):
    output = ""
    try:
        output += subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        output += e.output
        return (False, output)
    return (True, output)

def handle_JavaWithRunner(runner_name):
    output = ""
    did_run = True
    try:
        output += subprocess.check_output(["javac", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, output)

def run_program(directory, username, problem_id, filename):
    # Normally, the problems are defined in a DB (mongo, MySQL, etc.)
    problems = {"Song": {"type": "JavaWithRunner", "runner_name": "SongRunner"}}

    # Go deal with some file system stuff...
    filename, extension = (filename.split(".")[0], filename.split(".")[1])
    os.chdir("root")
    os.chdir(directory)
    print "Entering directory %s..."%directory

    output = ""
    if problems[problem_id]["type"] == "JavaWithRunner":
        shutil.copyfile("../../data/runners/%s.java"%problems[problem_id]["runner_name"], "./%s.java"%problems[problem_id]["runner_name"])
        result = handle_JavaWithRunner(problems[problem_id]["runner_name"])
        output = result[1]

    os.chdir("../..")
    return output

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
        return self

    def render_GET(self, request):
        return open("./static/index.html").read()

class UploadView(resource.Resource):
    isLeaf = True
    def render_POST(self, request):
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

        username = request.args["username"][0]
        problem_id = request.args["problem"][0]

        # Run it (or queue it for running, or whatever)
        #output = subprocess.check_output(["javac", "%s.java"%filename])
        #output += subprocess.check_output(["java", "%s"%filename])
        output = run_program(d, username, problem_id, filename+"."+extension)

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
