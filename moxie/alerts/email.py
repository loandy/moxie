#  Copyright (c) Paul R. Tagliamonte <tag@pault.ag>, 2015
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import asyncio
import smtplib

import jinja2
from aiocore import Service
from aiomultiprocessing import AsyncProcess


_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        '..', '..',
        'templates'
    ))
)

MOXIE_WEB_URL = os.environ.get("MOXIE_WEB_URL", "http://localhost:8888")


class EmailAlert:
    TYPES = ['failure']

    def __init__(self, host, user, password):
        self.db = Service.resolve("moxie.cores.database.DatabaseService")
        self.host = host
        self.user = user
        self.password = password

    def send(self, payload, job, maintainer, run):
        type_ = payload['type']

        server = smtplib.SMTP(self.host, 587)
        server.ehlo()
        server.starttls()
        server.login(self.user, self.password)

        template = _jinja_env.get_template("emails/{}.email".format(type_))
        body = template.render(user_name="Moxie",
                               user=self.user,
                               root=MOXIE_WEB_URL,
                               maintainer=maintainer,
                               job=job,
                               run=run)
        body = body.encode()  # Ready to send it over the line.

        server.sendmail(self.user, [maintainer.email], body)
        server.quit()

    @asyncio.coroutine
    def __call__(self, payload):
        type_ = payload['type']
        if type_ not in self.TYPES:
            return

        job = yield from self.db.job.get(payload.get("job"))
        maintainer = yield from self.db.maintainer.get(job.maintainer_id)
        runid = payload.get("result", None)
        run = None
        if runid:
            run = yield from self.db.run.get(runid)

        p = AsyncProcess(target=self.send, args=(payload, job, maintainer, run))
        p.start()
        yield from p.join()
