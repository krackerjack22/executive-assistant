set -a; source .env; set +a
echo "--- 1. Liability Waiver ---"
uv run python3 skills/pdf-form-autofill/autofill.py --template "tests/test_docs/signature_tests/Liability Waiver Guardian.pdf" --profile charlotte_combs --commit-unsafe --human --vision-qa

echo "--- 2. Player-Parent Agreement ---"
uv run python3 skills/pdf-form-autofill/autofill.py --template "tests/test_docs/signature_tests/2008 Player-Parent Agreement.pdf" --profile charlotte_combs --commit-unsafe --human --vision-qa

echo "--- 3. Special Meeting Minutes ---"
uv run python3 skills/pdf-form-autofill/autofill.py --template "tests/test_docs/signature_tests/Special Meeting Minutes from RareBird.pdf" --profile tyler_combs --commit-unsafe --human --vision-qa
