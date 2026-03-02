class Agtop < Formula
  include Language::Python::Virtualenv

  desc "Performance monitoring CLI tool for Apple Silicon"
  homepage "https://github.com/binlecode/agtop"
  url "https://github.com/binlecode/agtop/archive/refs/tags/v0.4.2.tar.gz"
  sha256 "5617a3897dfaa89e0fd637b82e9aa118126e04ec31615f0200c570f4ca7a8e2a"
  license "MIT"

  bottle do
    root_url "https://github.com/binlecode/agtop/releases/download/v0.4.2"
    rebuild 5
    sha256 cellar: :any_skip_relocation, arm64_tahoe:   "f28976576b20810841d1a8c377cab7f7969d362fc53dbf416cd769c68f63f299"
    sha256 cellar: :any_skip_relocation, arm64_sequoia: "c56786c8c3ff41f758d5d385ad3f6f1f52065ea742df6ad2a207ed613b0023d7"
    sha256 cellar: :any_skip_relocation, arm64_sonoma:  "0b6191cb8a1f83ee6ef23e02fe8154f53686241d153915309d7a5419ccd65ce9"
  end

  depends_on "python@3.13"

  resource "blessed" do
    url "https://files.pythonhosted.org/packages/e6/0c/658dea9ba35fcea19e6feaa8ba0d2dbf8cac9aeaa1f9ab1d77d36f534757/blessed-1.32.0.tar.gz"
    sha256 "d4090e9908cf86bea15a5275845c8bfc69c4c34eb6d22de07c65d26f1e54a918"
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
