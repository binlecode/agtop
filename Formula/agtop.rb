class Agtop < Formula
  include Language::Python::Virtualenv

  desc "Performance monitoring CLI tool for Apple Silicon"
  homepage "https://github.com/binlecode/agtop"
  url "https://github.com/binlecode/agtop/archive/refs/tags/v0.3.8.tar.gz"
  sha256 "926a4fef7cf418a6ddb861e63cee0640e66b2e976a58b85be4630366f01b53f5"
  license "MIT"

  bottle do
    root_url "https://github.com/binlecode/agtop/releases/download/v0.3.8"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_tahoe:   "388eaed1833f58a18976545d538d89849d98994162ede49c902e89b3fba73f3d"
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "eb105c882c63ee752bc4f138e58dad375dd0d354d35143efcfe3d0d56d6f8937"
    sha256 cellar: :any_skip_relocation, arm64_sonoma:  "2e39c88700a8c15735cfb1860e55b73d319e7f89e7612c43d486504e88010918"
  end

  depends_on "python@3.13"

  resource "blessed" do
    url "https://files.pythonhosted.org/packages/dd/19/e926a0dbbf93c7aeb15d4dfff0d0e3de02653b3ba540b687307d0819c1ff/blessed-1.30.0.tar.gz"
    sha256 "4d547019d7b40fc5420ea2ba2bc180fdccc31d6715298e2b49ffa7b020d44667"
  end

  resource "dashing" do
    url "https://files.pythonhosted.org/packages/bd/01/1c966934ab5ebe5a8fa3012c5de32bfa86916dba0428bdc6cdfe9489f768/dashing-0.1.0.tar.gz"
    sha256 "2514608e0f29a775dbd1b1111561219ce83d53cfa4baa2fe4101fab84fd56f1b"
  end

  resource "psutil" do
    url "https://files.pythonhosted.org/packages/aa/c6/d1ddf4abb55e93cebc4f2ed8b5d6dbad109ecb8d63748dd2b20ab5e57ebe/psutil-7.2.2.tar.gz"
    sha256 "0746f5f8d406af344fd547f1c8daa5f5c33dbc293bb8d6a16d80b4bb88f59372"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/35/a2/8e3becb46433538a38726c948d3399905a4c7cabd0df578ede5dc51f0ec2/wcwidth-0.6.0.tar.gz"
    sha256 "cdc4e4262d6ef9a1a57e018384cbeb1208d8abbc64176027e2c2455c81313159"
  end

  def install
    virtualenv_install_with_resources(using: "python@3.13")
  end

  test do
    output = shell_output("#{bin}/agtop --help")
    assert_match "Performance monitoring CLI tool for Apple Silicon", output
  end
end
