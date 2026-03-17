#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Dataset Validator (v1.1 Specter-Grade)

import h5py
import numpy as np
import unittest
import sys
import os

class TestVDFDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.environ.get('VDF_PATH', 'data/vdf_captures/phase1_expansion.h5')
        if not os.path.exists(cls.path):
            raise FileNotFoundError(f"Dataset not found at {cls.path}. Run the sequencer first.")
        cls.file = h5py.File(cls.path, 'r')
        cls.X = cls.file['X'][:]
        cls.Y = cls.file['Y'][:]
        cls.Z = cls.file['Z'][:]

    @classmethod
    def tearDownClass(cls):
        cls.file.close()

    def test_dataset_shapes(self):
        """Verify the 'Trinity' of dataset shapes."""
        N = self.X.shape[0]
        self.assertEqual(self.X.shape, (N, 1024, 2), "X must be (N, 1024, 2)")
        self.assertEqual(self.Y.shape, (N, 24), "Y must be (N, 24) one-hot")
        self.assertEqual(self.Z.shape, (N, 8), "Z must be (N, 8) metadata")

    def test_numerical_stability(self):
        """Ensure no NaNs or Infinities exist in the dataset."""
        self.assertFalse(np.isnan(self.X).any(), "Dataset X contains NaNs")
        self.assertFalse(np.isinf(self.X).any(), "Dataset X contains Infinities")

    def test_normalization_integrity(self):
        """Verify that the Soft-Clip normalization is effective."""
        max_amp = np.max(np.abs(self.X))
        self.assertLess(max_amp, 1.0, f"Normalization failed: Max amplitude {max_amp} >= 1.0")
        mean_pwr = np.mean(self.X[:, :, 0]**2 + self.X[:, :, 1]**2)
        self.assertGreater(mean_pwr, 0.05, f"Signal too weak: Mean power {mean_pwr} < 0.05")

    def test_label_validity(self):
        """Verify one-hot encoding for Y."""
        row_sums = np.sum(self.Y, axis=1)
        self.assertTrue(np.allclose(row_sums, 1.0), "Y labels are not properly one-hot encoded")

    def test_metadata_consistency(self):
        """Verify Z matrix contains valid range data."""
        snrs = self.Z[:, 0]
        self.assertTrue(np.all(snrs >= 0), "Negative SNR detected")
        sps = self.Z[:, 3]
        self.assertTrue(np.all(sps >= 1), "Invalid Samples Per Symbol (SPS) < 1")

    def test_spectral_variance(self):
        """Verify the snapshots have spectral content (not just DC/Silence)."""
        idx = np.random.randint(0, self.X.shape[0])
        complex_samples = self.X[idx, :, 0] + 1j * self.X[idx, :, 1]
        spectrum = np.abs(np.fft.fft(complex_samples))
        variance = np.var(spectrum)
        self.assertGreater(variance, 1e-5, "Snapshot lacks spectral variance (likely silence or DC)")

    def test_hdf5_attributes(self):
        """Ensure Sigma Hardening attributes are present."""
        self.assertIn('mission_id', self.file.attrs, "Missing 'mission_id' attribute")

if __name__ == '__main__':
    unittest.main()
