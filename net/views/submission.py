import shutil
import os, errno
import hashlib
import tempfile
import math
import urllib
import urllib2

from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, QueryDict
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import Context, RequestContext, loader
from django.contrib.auth.decorators import login_required

from astrometry.net.models import *
from astrometry.net import settings
from log import *
from django import forms
from django.http import HttpResponseRedirect

from astrometry.util import image2pnm
from astrometry.util.run_command import run_command


def index(req, user_id):
    if user_id == None:
        submissions = Submission.objects.all()
    else:
        submissions = Submission.objects.filter(user=user_id)
    
    context = {'submissions':submissions}
    return render_to_response('submissions_list.html', context,
        context_instance = RequestContext(req))

class UploadFileForm(forms.Form):
    file  = forms.FileField()

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            sub = handle_uploaded_file(request, request.FILES['file'])
            return redirect(status, subid=sub.id)
    else:
        form = UploadFileForm()
    return render_to_response('upload.html', {'form': form, 'user': request.user },
        context_instance = RequestContext(request))

def status(req, subid=None):
    logmsg("Submissions: " + ', '.join([str(x) for x in Submission.objects.all()]))

    #if subid is not None:
    #    # strip leading zeros
    #    subid = int(subid.lstrip('0'))
    sub = get_object_or_404(Submission, pk=subid)

    # Would be convenient to have an "is this a single-image submission?" function
    # (This is really "UserImage" status, not Submission status)

    #logmsg("UserImages: " + ', '.join(['%i'%s.id for s in sub.user_images.all()]))

    logmsg("UserImages:")
    for ui in sub.user_images.all():
        logmsg("  %i" % ui.id)
        for j in ui.jobs.all():
            logmsg("    job " + str(j))

    job = None
    calib = None
    jobs = sub.get_best_jobs()
    logmsg("Best jobs: " + str(jobs))
    if len(jobs) == 1:
        job = jobs[0]
        logmsg("Job: " + str(job) + ', ' + job.status)
        calib = job.calibration
        
    return render_to_response('status.html', { 'sub': sub, 'job': job, 'calib':calib, },
        context_instance = RequestContext(req))
    
def handle_uploaded_file(req, f):
    logmsg('handle_uploaded_file: req=' + str(req))
    logmsg('handle_uploaded_file: req.session=' + str(req.session))
    #logmsg('handle_uploaded_file: req.session.user=' + str(req.session.user))
    logmsg('handle_uploaded_file: req.user=' + str(req.user))

    # get file onto disk
    file_hash = DiskFile.get_hash()
    temp_file_path = tempfile.mktemp()
    uploaded_file = open(temp_file_path, 'wb+')
    for chunk in f.chunks():
        uploaded_file.write(chunk)
        file_hash.update(chunk)
    uploaded_file.close()
    # move file into data directory
    DiskFile.make_dirs(file_hash.hexdigest())
    shutil.move(temp_file_path, DiskFile.get_file_path(file_hash.hexdigest()))
    # create and populate the database entry
    df = DiskFile(file_hash = file_hash.hexdigest(), size=0, file_type='')
    df.set_size_and_file_type()
    df.save()

    # HACK
    submittor = req.user if req.user.is_authenticated() else None
    sub = Submission(user=submittor, disk_file=df, scale_type='ul', scale_units='degwidth')
    sub.original_filename = f.name
    sub.save()
    logmsg('Made Submission' + str(sub))

    return sub
