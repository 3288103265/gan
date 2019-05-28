# coding=utf-8
# Copyright 2019 The TensorFlow GAN Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for stargan.train."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl import flags
import numpy as np
import tensorflow as tf
import tensorflow_gan as tfgan

from tensorflow_gan.examples.stargan import train

tf.compat.v1.disable_v2_behavior()
FLAGS = flags.FLAGS
mock = tf.compat.v1.test.mock


def _test_generator(input_images, _):
  """Simple generator function."""
  return input_images * tf.compat.v1.get_variable(
      'dummy_g', initializer=2.0, use_resource=False)


def _test_discriminator(inputs, num_domains):
  """Differentiable dummy discriminator for StarGAN."""
  hidden = tf.compat.v1.layers.flatten(inputs)
  output_src = tf.reduce_mean(input_tensor=hidden, axis=1)
  output_cls = tf.compat.v1.layers.dense(inputs=hidden, units=num_domains)

  return output_src, output_cls


train.network.generator = _test_generator
train.network.discriminator = _test_discriminator


class TrainTest(tf.test.TestCase):

  def test_define_model(self):
    FLAGS.batch_size_stargan = 2
    images_shape = [FLAGS.batch_size_stargan, 4, 4, 3]
    images_np = np.zeros(shape=images_shape)
    images = tf.constant(images_np, dtype=tf.float32)
    labels = tf.one_hot([0] * FLAGS.batch_size_stargan, 2)

    model = train._define_model(images, labels)
    self.assertIsInstance(model, tfgan.StarGANModel)
    self.assertShapeEqual(images_np, model.generated_data)
    self.assertShapeEqual(images_np, model.reconstructed_data)
    self.assertTrue(isinstance(model.discriminator_variables, list))
    self.assertTrue(isinstance(model.generator_variables, list))
    self.assertIsInstance(model.discriminator_scope, tf.compat.v1.VariableScope)
    self.assertTrue(model.generator_scope, tf.compat.v1.VariableScope)
    self.assertTrue(callable(model.discriminator_fn))
    self.assertTrue(callable(model.generator_fn))

  @mock.patch.object(
      tf.compat.v1.train, 'get_or_create_global_step', autospec=True)
  def test_get_lr(self, mock_get_or_create_global_step):
    FLAGS.max_number_of_steps_stargan = 10
    base_lr = 0.01
    with self.test_session(use_gpu=True) as sess:
      mock_get_or_create_global_step.return_value = tf.constant(2)
      lr_step2 = sess.run(train._get_lr(base_lr))
      mock_get_or_create_global_step.return_value = tf.constant(9)
      lr_step9 = sess.run(train._get_lr(base_lr))

    self.assertAlmostEqual(base_lr, lr_step2)
    self.assertAlmostEqual(base_lr * 0.2, lr_step9)

  def test_define_train_ops(self):
    FLAGS.batch_size_stargan = 2
    FLAGS.generator_lr = 0.1
    FLAGS.discriminator_lr = 0.01

    images_shape = [FLAGS.batch_size_stargan, 4, 4, 3]
    images = tf.zeros(images_shape, dtype=tf.float32)
    labels = tf.one_hot([0] * FLAGS.batch_size_stargan, 2)

    model = train._define_model(images, labels)
    loss = tfgan.stargan_loss(model)
    train_ops = train._define_train_ops(model, loss)

    self.assertIsInstance(train_ops, tfgan.GANTrainOps)

  def test_get_train_step(self):
    FLAGS.gen_disc_step_ratio_stargan = 0.5
    train_steps = train._define_train_step()
    self.assertEqual(1, train_steps.generator_train_steps)
    self.assertEqual(2, train_steps.discriminator_train_steps)

    FLAGS.gen_disc_step_ratio_stargan = 3
    train_steps = train._define_train_step()
    self.assertEqual(3, train_steps.generator_train_steps)
    self.assertEqual(1, train_steps.discriminator_train_steps)

  @mock.patch.object(train.data_provider, 'provide_data', autospec=True)
  def test_main(self, mock_provide_data):
    FLAGS.max_number_of_steps_stargan = 10
    FLAGS.batch_size_stargan = 2
    num_domains = 3

    # Construct mock inputs.
    images_shape = [FLAGS.batch_size_stargan, FLAGS.patch_size_stargan, FLAGS.patch_size_stargan, 3]
    img_list = [tf.zeros(images_shape)] * num_domains
    lbl_list = [tf.one_hot([0] * FLAGS.batch_size_stargan, num_domains)] * num_domains
    mock_provide_data.return_value = (img_list, lbl_list)

    train.main(None)


if __name__ == '__main__':
  tf.test.main()
