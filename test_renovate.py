from click.testing import CliRunner

from renovate import cli


def test_renovate():
  runner = CliRunner()
  result = runner.invoke(cli, ['--cluster-path', './tests/'])
  assert result.exit_code == 0
  assert result.output == 'Hello Peter!\n'
