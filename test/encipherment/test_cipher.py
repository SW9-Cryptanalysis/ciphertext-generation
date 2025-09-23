import pytest

@pytest.fixture
def sample_text_legal():
	return ('thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong'
			'enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothistweneedtoensure'
			'thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest'
		 	'theperformanceoftheciphergenerationprocess')
	
@pytest.fixture
def sample_texts_illegal():
	return ['ThisTextHasUppercaseLettersAnd12345Numbers!@#',
			'This text has spaces',
			'this-text-has-dashes',
			'this.text.has.punctuation!',
			]
	
def test_legal_plaintext(sample_text_legal):
	from encipherment.cipher import Cipher
	cipher = Cipher(sample_text_legal)
	assert cipher.plaintext == sample_text_legal
	assert 4 <= cipher.difficulty <= 10
	assert isinstance(cipher.key, dict)
	assert all(isinstance(v, list) for v in cipher.key.values())
	assert isinstance(cipher.ciphertext, str)
	assert all(num.isdigit() for num in cipher.ciphertext.split())
 
def test_illegal_plaintext(sample_texts_illegal):
	from encipherment.cipher import Cipher
	for text in sample_texts_illegal:
		with pytest.raises(ValueError) as excinfo:
			Cipher(text)
		assert "Plaintext must contain only lowercase letters with no punctuation or spaces." in str(excinfo.value)