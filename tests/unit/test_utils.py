# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import pathlib
import unittest
from unittest import mock

import yaml
from jujubackupall.config import Config

from tests.fixtures import (
    ACCOUNTS_YAML,
    MOCK_CONFIG,
    RAW_PUBKEY,
    SSH_FINGERPRINT,
    MockController,
    MockModel,
)
from utils import SSHKeyHelper


class TestUtils(unittest.TestCase):
    """Utils test class."""

    @classmethod
    def setUpClass(cls):
        """Set up class fixture."""
        # patch relevant modules/methods
        cls.nrpe_support_patcher = mock.patch("utils.NRPE")
        cls.nrpe_support_patcher.start()

        cls.charm_dir_patcher = mock.patch("charmhelpers.core.hookenv.charm_dir")
        patch = cls.charm_dir_patcher.start()
        patch.return_value = str(pathlib.Path(__file__).parents[2].absolute())

    def setUp(self):
        """Set up tests."""
        self.model = mock.Mock()
        self.helper = SSHKeyHelper(
            Config(args=MOCK_CONFIG),
            yaml.safe_load(ACCOUNTS_YAML)["controllers"],
        )

    def test_gen_libjuju_ssh_key_fingerprint_invalid(self):
        """Test the ssh fingerprint generation."""
        with self.assertRaises(ValueError):
            self.helper._gen_libjuju_ssh_key_fingerprint(raw_pubkey="")

    def test_gen_libjuju_ssh_key_fingerprint_valid(self):
        """Test the ssh fingerprint generation."""
        self.assertEqual(
            self.helper._gen_libjuju_ssh_key_fingerprint(raw_pubkey=RAW_PUBKEY),
            SSH_FINGERPRINT,
        )

    @mock.patch("utils.run_async")
    def test_get_model_ssh_key_fingeprints(self, mock_run_async):
        """Test the getting the model ssh fingerprint."""
        result = "mock fingerprint"
        mock_run_async.return_value = {"results": [{"result": result}]}
        self.assertEqual(
            self.helper._get_model_ssh_key_fingeprints(self.model),
            result,
        )

    @mock.patch("utils.BackupProcessor")
    @mock.patch("utils.connect_model")
    @mock.patch("utils.connect_controller")
    @mock.patch("utils.Paths.SSH_PUBLIC_KEY")
    def test_push_ssh_keys_to_models(
        self,
        mock_pubkey_path,
        mock_connect_controller,
        mock_connect_model,
        mock_backup_processor,
    ):
        """Parameterized test for ssh key push."""
        new_key = RAW_PUBKEY.replace("jujubackup", "newuser")
        params = [
            (
                "test with existing key (should not add)",
                RAW_PUBKEY,
                lambda mock_obj: mock_obj.assert_not_called(),
            ),
            (
                "test with missing key (should add)",
                new_key,
                lambda mock_obj: mock_obj.assert_called_with("admin", new_key),
            ),
        ]

        test_controller_name = "test-controller"
        mock_backup_processor.return_value.controller_names = [test_controller_name]
        mock_connect_controller.return_value.__enter__.return_value = MockController
        mock_connect_model.return_value.__enter__.return_value = MockModel

        for msg, ssh_pubkey, add_ssh_keys_test in params:
            with self.subTest(msg):
                mock_pubkey_path.read_text.return_value = ssh_pubkey
                self.helper.push_ssh_keys_to_models()

                mock_pubkey_path.read_text.assert_called()
                mock_backup_processor.assert_called_once()
                mock_connect_controller.assert_called_once_with(test_controller_name)
                MockController.list_models.assert_called_once()
                mock_connect_model.assert_called_once_with(MockController, "test-model")
                MockModel.get_ssh_keys.assert_called_once()
                add_ssh_keys_test(MockModel.add_ssh_keys)

            # reset mocks at the end of each test iteration
            mock_connect_controller.reset_mock()
            mock_connect_model.reset_mock()
            mock_backup_processor.reset_mock()
            MockController.list_models.reset_mock()
            MockModel.get_ssh_keys.reset_mock()
            MockModel.add_ssh_keys.reset_mock()