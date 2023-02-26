#!/usr/bin/env ruby

require 'optparse'
require 'logger'
require 'yaml'
require 'pathname'
require 'byebug'
require_relative 'scanner'
require_relative 'img2pdf'


$logger = Logger.new(STDOUT)
$logger.level = 0
$options = {}

BATCH_THRESHOLD_IN_SECONDS = 600 # 10mins

OptionParser.new do |opts|
  [:outputdir, :prefix, :timestamp, :resolution, :height, :width, :mode, :source, :duplex].each do |argument|
    opts.on("--#{argument} [String]") do |arg_value|
      $options[argument] = arg_value
    end
  end

end.parse!

class BatchScan
  include Scanner
  include Img2pdf

  attr_reader :current_job
  JOBS_FILE = (Pathname.new($options[:outputdir]) + ".jobs.yml").freeze
  def initialize
    begin
      @current_job = YAML.load_file(JOBS_FILE) || {}
    rescue Errno::ENOENT
      File.new(JOBS_FILE, "w").close
      @current_job = {}
    end

    $logger.debug( "Current job yaml: #{@current_job}" )
    run_scan
  end

  def run_scan
    if is_duplex?
      $logger.info("duplex mode")
      if active_job?
        # Scan even pages
        batch_template = batch_template(outputdir: $options[:outputdir], prefix: $options[:prefix], timestamp: @current_job[:timestamp])
        @current_job[:files] = scan(resolution: $options[:resolution], batch_template: batch_template, batch_start: 2, batch_increment: 2, mode: $options[:mode], source: $options[:source])
        # Assuming we are flipping the stack, the even pages will be in reverse order
        reverse_even_pages
        combine_and_finalize
      else
        # Scan odd pages
        batch_template = batch_template(outputdir: $options[:outputdir], prefix: $options[:prefix], timestamp: $options[:timestamp])
        @current_job[:files] = scan(resolution: $options[:resolution], batch_template: batch_template, batch_start: 1, batch_increment: 2, mode: $options[:mode], source: $options[:source])
        @current_job[:timestamp] = $options[:timestamp]
        finalize
      end
    else
      $logger.info("non-duplex mode")
      batch_template = batch_template(outputdir: $options[:outputdir], prefix: $options[:prefix], timestamp: $options[:timestamp])
      @current_job[:files] = scan(resolution: $options[:resolution], batch_template: batch_template, batch_start: 1, batch_increment: 1, mode: $options[:mode], source: $options[:source])
      @current_job[:timestamp] = $options[:timestamp]
      @current_job[:files].sort
      combine_and_finalize
    end
  end

  def timestamp
    @current_job[:timestamp]
  end

  def combine_and_finalize
    filepath = combine(@current_job[:files]) unless @current_job[:files].empty?
    $logger.error("skipping combine! No files found") if @current_job[:files].empty?
    @current_job = {}
    finalize
    $logger.info("Final filepath: #{filepath}")
  end

  def reverse_even_pages
    even_index = @current_job[:files].size - 1
    even_index -= 1 unless even_index % 2 == 1

    @current_job[:files].each_with_index do |file, index|
      if index % 2 == 0
        # odd pages
        files << file
      else
        files << @current_job[:files][even_index]
        even_index -= 2
      end
    end
    @current_job[:files] = files
  end

  def finalize
    File.open(JOBS_FILE, 'w') do |out|
      YAML.dump(@current_job, out)
    end
  end

  def is_duplex?
    $options[:duplex].to_s.downcase == "true"
  end

  def active_job?
    return false if @current_job.empty?
    !!@current_job[:timestamp] && !expired_job?
  end

  def expired_job?
    raise unless @current_job[:timestamp]
    $logger.debug("timestamp differences: #{($options[:timestamp].to_i - @current_job[:timestamp].to_i)}")
    ($options[:timestamp].to_i - @current_job[:timestamp].to_i) > BATCH_THRESHOLD_IN_SECONDS
  end
end

$logger.info $options
BatchScan.new
