import pytest
from backend.ingestion.cdm import parse_cdm_kvn, parse_cdm_xml, CDMValidationError

VALID = '''CCSDS_CDM_VERS = 1.0
CREATION_DATE = 2026-11-27T00:00:00Z
ORIGINATOR = TEST
MESSAGE_ID = ABC-1
TCA = 2026-12-01T12:00:00Z
MISS_DISTANCE = 840
RELATIVE_SPEED = 12000
OBJECT = OBJECT1
OBJECT_DESIGNATOR = 900
OBJECT = OBJECT2
OBJECT_DESIGNATOR = 901
'''

VALID_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<cdm version="1.0"><header><CREATION_DATE>2026-11-27T00:00:00Z</CREATION_DATE>
<ORIGINATOR>TEST</ORIGINATOR><MESSAGE_ID>XML-1</MESSAGE_ID></header>
<body><relativeMetadataData><TCA>2026-12-01T12:00:00Z</TCA>
<MISS_DISTANCE units="m">840</MISS_DISTANCE><RELATIVE_SPEED units="m/s">12000</RELATIVE_SPEED>
</relativeMetadataData><segment><metadata><OBJECT>OBJECT1</OBJECT>
<OBJECT_DESIGNATOR>900</OBJECT_DESIGNATOR></metadata><data><covarianceMatrix>
<CR_R>1.5</CR_R></covarianceMatrix></data></segment>
<segment><metadata><OBJECT>OBJECT2</OBJECT><OBJECT_DESIGNATOR>901</OBJECT_DESIGNATOR>
</metadata><data><covarianceMatrix><CR_R>2.5</CR_R></covarianceMatrix></data></segment>
</body></cdm>'''


def test_xml_cdm_preserves_fields_covariance_and_units():
    result = parse_cdm_xml(VALID_XML)
    assert result['external_id'] == 'XML-1'
    assert result['miss_distance_m'] == 840
    assert result['covariance_present'] is True
    assert result['objects'][0]['COVARIANCE_MATRIX']['CR_R'] == '1.5'
    assert result['xml_units']['MISS_DISTANCE']['units'] == 'm'


@pytest.mark.parametrize('content', [
    VALID_XML.replace('<TCA>2026-12-01T12:00:00Z</TCA>', ''),
    VALID_XML.replace('2026-12-01T12:00:00Z', 'not-a-date'),
    VALID_XML.replace('<OBJECT_DESIGNATOR>901</OBJECT_DESIGNATOR>', ''),
    '<!DOCTYPE cdm [<!ENTITY x "bad">]>' + VALID_XML.replace('<?xml version="1.0" encoding="UTF-8"?>', ''),
])
def test_invalid_xml_cdm_rejected(content):
    with pytest.raises(CDMValidationError):
        parse_cdm_xml(content)

def test_valid_cdm_preserves_provider_values():
    result = parse_cdm_kvn(VALID)
    assert result['miss_distance_m'] == 840
    assert result['relative_speed_m_s'] == 12000
    assert [item['OBJECT_DESIGNATOR'] for item in result['objects']] == ['900', '901']
    assert result['provider_collision_probability'] is None

def test_cdm_with_section_markers_and_missing_covariance():
    marked = VALID.replace('OBJECT = OBJECT1', 'META_START\nOBJECT = OBJECT1\nMETA_STOP\nDATA_START')
    marked = marked.replace('OBJECT = OBJECT2', 'DATA_STOP\nMETA_START\nOBJECT = OBJECT2\nMETA_STOP\nDATA_START')
    result = parse_cdm_kvn(marked + 'DATA_STOP\n')
    assert result['covariance_present'] is False

@pytest.mark.parametrize('content', [
    VALID.replace('MISS_DISTANCE = 840\n', ''),
    VALID.replace('2026-12-01T12:00:00Z', 'yesterday'),
    VALID.replace('MISS_DISTANCE = 840', 'MISS_DISTANCE = -1'),
    VALID.replace('OBJECT = OBJECT2', 'OBJECT = OBJECT1'),
])
def test_invalid_cdm_rejected(content):
    with pytest.raises(CDMValidationError):
        parse_cdm_kvn(content)
