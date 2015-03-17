"""
 .. autoclass:: server.tests.processor.base.BaseProcessorTestCase
    :members: run_processor, assertFields, assertFiles, assertJSON

"""
from __future__ import print_function

import hashlib
import gzip
import os
import shutil

from django.conf import settings
from django.core import management
from django.test import TestCase

from genesis.models import GenUser
from server.models import Data, Storage, Processor, iterate_fields
from server.tasks import manager
from ..unit.utils import create_admin, create_test_case


PROCESSORS_FIXTURE_CACHE = None


def _register_processors():
    Processor.objects.delete()

    global PROCESSORS_FIXTURE_CACHE  # pylint: disable=global-statement
    if PROCESSORS_FIXTURE_CACHE:
        Processor.objects.insert(PROCESSORS_FIXTURE_CACHE)
    else:
        if len(GenUser.objects.filter(is_superuser=True)) == 0:
            GenUser.objects.create_superuser(email='admin@genialis.com')

        management.call_command('register', force=True, verbosity='0')
        PROCESSORS_FIXTURE_CACHE = Processor.objects.all()
        for p in PROCESSORS_FIXTURE_CACHE:
            # Trick Mongoengine not to fail the insert
            p._created = True  # pylint: disable=protected-access


class BaseProcessorTestCase(TestCase):

    """Base class for writing processor tests.

    This class is subclass of Django's ``TestCase`` with some specific
    functions used for testing processors.

    To write a processor test use standard Django's syntax for writing
    tests and follow next steps:

    #. Put input files (if any) in ``server/tests/processor/inputs``
       folder.
    #. Run test with :func:`run_processor`.
    #. Check if processor has finished successfully with
       :func:`assertDone` function.
    #. Assert processor's output with :func:`assertFiles`,
       :func:`assertFields` and :func:`assertJSON` functions.

    .. DANGER::
        If output files doesn't exists in
        ``server/tests/processor/outputs`` folder, they are created
        automatically. But you have to chack that they are correct
        before using them for further runs.

    """

    def setUp(self):
        super(BaseProcessorTestCase, self).setUp()
        self.admin = create_admin()
        _register_processors()

        self.case = create_test_case(self.admin.pk)['c1']
        self.current_path = os.path.dirname(os.path.abspath(__file__))

    def tearDown(self):
        super(BaseProcessorTestCase, self).tearDown()

        # Delete Data objects and their files
        for d in Data.objects.all():
            data_dir = os.path.join(settings.DATAFS['data_path'], str(d.pk))
            d.delete()
            shutil.rmtree(data_dir, ignore_errors=True)

    def run_processor(self, processor_name, input_, assert_status=Data.STATUS_DONE):
        """Runs given processor with specified inputs.

        If input is file, file path should be given relative to
        ``server/tests/processor/inputs`` folder.
        If ``assert_status`` is given check if Data object's status
        matches ``assert_status`` after finishing processor.

        :param processor_name: name of the processor to run
        :type processor_name: :obj:`str`

        :param ``input_``: Input paramaters for processor. You don't
            have to specifie parameters for which default values are
            given.
        :type ``input_``: :obj:`dict`

        :param ``assert_status``: Desired status of Data object
        :type ``assert_status``: :obj:`str`

        :return: :obj:`server.models.Data` object which is created by
            the processor.

        """
        p = Processor.objects.get(name=processor_name)

        for field_schema, fields in iterate_fields(input_, p['input_schema']):
            # copy referenced files to upload dir
            if field_schema['type'] == "basic:file:":
                old_path = os.path.join(self.current_path, 'inputs', fields[field_schema['name']])
                shutil.copy2(old_path, settings.FILE_UPLOAD_TEMP_DIR)
                file_name = os.path.basename(fields[field_schema['name']])
                fields[field_schema['name']] = {
                    'file': file_name,
                    'file_temp': file_name,
                    'is_remote': False,
                }

            # convert primary keys to strings
            if field_schema['type'].startswith('data:'):
                fields[field_schema['name']] = str(fields[field_schema['name']])
            if field_schema['type'].startswith('list:data:'):
                fields[field_schema['name']] = [str(obj) for obj in fields[field_schema['name']]]

        d = Data(
            input=input_,
            author_id=self.admin.pk,
            processor_name=processor_name,
            case_ids=[self.case.pk],
        )
        d.save()
        manager(run_sync=True, verbosity=0)

        # Fetch latest Data object from database
        d = Data.objects.get(pk=d.pk)

        if assert_status:
            self._assertStatus(d, assert_status)

        return d

    def _assertStatus(self, obj, status):  # pylint: disable=invalid-name
        """Check if Data object's status is 'status'.

        :param obj: Data object for which to check status
        :type obj: :obj:`server.models.Data`
        :param status: Data status to check
        :type status: str

        """
        self.assertEqual(obj.status, status, msg="Data status != '{}'".format(status) + self._msg_stdout(obj))

    def assertFields(self, obj, path, value):  # pylint: disable=invalid-name
        """Compare Data object's field to given value.

        :param obj: Data object with field to compare
        :type obj: :obj:`server.models.Data`

        :param path: Path to field in Data object.
        :type path: :obj:`str`

        :param value: Desired value.
        :type value: :obj:`str`

        """
        field = self._get_field(obj['output'], path)
        self.assertEqual(field, str(value),
                         msg="Field 'output.{}' mismatch: {} != {}".format(path, field, str(value)) +
                         self._msg_stdout(obj))

    def assertFiles(self, obj, field_path, fn, gzipped=False):  # pylint: disable=invalid-name
        """Compare output file of a processor to the given correct file.

        :param obj: Data object which includes file that we want to
            compare.
        :type obj: :obj:`server.models.Data`

        :param field_path: Path to file name in Data object.
        :type field_path: :obj:`str`

        :param fn: File name (and relative path) of file to which we
            want to compare. Name/path is relative to
            'server/tests/processor/outputs'.
        :type fn: :obj:`str`

        :param gzipped: If true, file is unziped before comparison.
        :type gzipped: :obj:`bool`

        """
        field = self._get_field(obj['output'], field_path)
        output = os.path.join(settings.DATAFS['data_path'], str(obj.pk), field['file'])
        output_file = gzip.open(output, 'rb') if gzipped else open(output)
        output_hash = hashlib.sha256(output_file.read()).hexdigest()

        wanted = os.path.join(self.current_path, 'outputs', fn)

        if not os.path.isfile(wanted):
            shutil.copyfile(output, wanted)
            self.fail(msg="Output file {} missing so it was created.".format(fn))

        wanted_file = gzip.open(wanted, 'rb') if gzipped else open(wanted)
        wanted_hash = hashlib.sha256(wanted_file.read()).hexdigest()
        self.assertEqual(wanted_hash, output_hash,
                         msg="File hash mismatch: {} != {}".format(wanted_hash, output_hash) + self._msg_stdout(obj))

    def assertJSON(self, obj, storage, field_path, fn):  # pylint: disable=invalid-name
        """Compare JSON in Storage object to the given correct output.

        :param obj: Data object which includes file that we want to
            compare.
        :type obj: :obj:`server.models.Data`

        :param storage: Storage (or storage id) which contains JSON to
            compare.
        :type storage: :obj:`server.models.Storage` or :obj:`str`

        :param field_path: Path to JSON subset to compare in Storage
            object. If it is empty, entire Storage object will be
            compared.
        :type field_path: :obj:`str`

        :param fn: File name (and relative path) of file to which we
            want to compare. Name/path is relative to
            'server/tests/processor/outputs'.
        :type fn: :obj:`str`

        """
        if type(storage) is not Storage:
            storage = Storage.objects.get(pk=str(storage))

        field = str(self._get_field(storage['json'], field_path))
        field_hash = hashlib.sha256(field).hexdigest()

        wanted = os.path.join(self.current_path, 'outputs', fn)

        if not os.path.isfile(wanted):
            with open(wanted, 'w') as fn:
                fn.write(field)

            self.fail(msg="Output file {} missing so it was created.".format(fn))

        wanted_hash = hashlib.sha256(open(wanted).read()).hexdigest()
        self.assertEqual(wanted_hash, field_hash,
                         msg="JSON hash mismatch: {} != {}".format(wanted_hash, field_hash) + self._msg_stdout(obj))

    def _get_field(self, obj, path):
        """Get field value ``path`` in multilevel dict ``obj``."""
        if len(path):
            for p in path.split('.'):
                obj = obj[p]
        return obj

    def _msg_stdout(self, data):
        msg = "\n\nDump stdout.txt:\n\n"
        stdout = os.path.join(settings.DATAFS['data_path'], str(data.pk), 'stdout.txt')
        if os.path.isfile(stdout):
            with open(stdout, 'r') as fn:
                msg += fn.read()

        return msg
