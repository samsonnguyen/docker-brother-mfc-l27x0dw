module Img2pdf

  def combine(files)
    raise if files.empty?
    $logger.debug("img2pdf --output '#{output_filepath}' #{files.join(" ")}")
    IO.popen("img2pdf --output '#{output_filepath}' #{files.join(" ")}") do |f|
      f.each do |line|
        $logger.info f.readlines
      end
    end
    output_filepath
  end
  
  def output_filepath
    (Pathname.new($options[:outputdir]) / "#{$options[:prefix]}-#{timestamp}.pdf").to_s
  end
end
