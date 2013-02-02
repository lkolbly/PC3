from twisted.internet import reactor
from twisted.web.server import Site, resource
from twisted.web.static import File
from twisted.python import log
import cgi, sys, os, subprocess

log.startLogging(sys.stdout)

class Root(resource.Resource):
    isLeaf = False

import re, StringIO, random, hashlib

def call_command(cmd):
    output = ""
    try:
        output += subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        output += e.output
        return (False, output)
    return (True, output)

# This class holds the concept of a "problem" that students are solving by
# uploading all of these files.
class Problem:
    def run_on_testcase(self, testcase):
        pass

    def run(self):
        return call_command("java HelloWorld")

def run_program(directory, filename):
    filename, extension = (filename.split(".")[0], filename.split(".")[1])
    os.chdir("root")
    os.chdir(directory)
    print "Entering directory %s..."%directory

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
            p = Problem()
            output += p.run()[1]

        pass
    else:
        output = ""
        try:
            output += subprocess.check_output(["javac", "%s.java"%filename], stderr=subprocess.STDOUT)
            output += subprocess.check_output(["java", "%s"%filename], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            output += e.output

    os.chdir("../..")
    return output

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

        # Run it (or queue it for running, or whatever)
        #output = subprocess.check_output(["javac", "%s.java"%filename])
        #output += subprocess.check_output(["java", "%s"%filename])
        output = run_program(d, filename+"."+extension)
        return output

root = Root()
root.putChild("upload", UploadView())
root.putChild("static", File("static/"))
site = Site(root)
reactor.listenTCP(8005, site)
reactor.run()
