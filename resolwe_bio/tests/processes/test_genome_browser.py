# pylint: disable=missing-docstring
from resolwe.test import tag_process
from django.conf import settings
from django.test import override_settings

from resolwe_bio.utils.test import BioProcessTestCase


class GenomeBrowserProcessorTestCase(BioProcessTestCase):

    @override_settings(RESOLWE_HOST_URL='https://dummy.host.com')
    @tag_process('igv')
    def test_igv_bam(self):
        print("Value of RESOLWE_HOST_URL setting:", settings.RESOLWE_HOST_URL)
        with self.preparation_stage():
            bam = self.prepare_bam()

            inputs = {'src': 'reads.bam'}
            bam1 = self.run_process('upload-bam', inputs)

        inputs = {
            'genomeid': 'hg19',
            'bam': [bam.pk, bam1.pk],
            'locus': 'chr7:79439229-79481604'
        }

        igv_session = self.run_process('igv', inputs)

        # remove resource path lines that have changing data object ids
        def filter_resource(line):
            if '<Resource path="{}/data/'.format(settings.RESOLWE_HOST_URL).encode('utf-8') in line:
                return True

        self.assertFile(igv_session, 'igv_file', 'igv_session_bam.xml', file_filter=filter_resource)
