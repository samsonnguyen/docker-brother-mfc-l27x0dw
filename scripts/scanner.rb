require 'pathname'
require 'fileutils'

module Scanner
  def scan(resolution: 300, batch_template:, batch_start: 1, batch_increment: 2, mode: , source: )
    $logger.debug("scanimage -v -v -p --batch='#{batch_template}' --batch-start #{batch_start} --batch-increment #{batch_increment} --resolution #{resolution} --mode '#{mode}' --source '#{source}' --format jpg")
    IO.popen("scanimage -v -v -p --batch='#{batch_template}' --batch-start #{batch_start} --batch-increment #{batch_increment} --resolution #{resolution} --mode '#{mode}' --source '#{source}' --format jpg") do |f|  
      f.each do |line|
        $logger.info f.readlines
      end
    end
    files = files_from_scan(batch_template)
    $logger.info files
    files
  end

  def batch_template(outputdir:, prefix:, timestamp:, ensure_dir: true)
    FileUtils.mkdir_p(Pathname.new(outputdir) / "#{prefix}" / "#{timestamp}") if ensure_dir
    (Pathname.new(outputdir) / "#{prefix}" / "#{timestamp}" / "#{prefix}-part-%03d.jpg").to_s
  end

  private
  def files_from_scan(template)
    Dir.glob(template.gsub("%03d", "*"))
  end

end
