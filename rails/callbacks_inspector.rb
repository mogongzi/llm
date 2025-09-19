#!/usr/bin/env ruby
# frozen_string_literal: true

# Rails runner script: inspect callbacks, touches, and dependents for a model
# Usage: bin/rails runner /path/to/callbacks_inspector.rb ModelName

require 'json'

def safe_constantize(name)
  Object.const_get(name)
rescue NameError
  nil
end

def extract_callbacks(klass, chain_sym, event_label)
  list = []
  return list unless klass.respond_to?(chain_sym)

  klass.send(chain_sym).each do |cb|
    begin
      kind = (cb.respond_to?(:kind) ? cb.kind : nil)
      filter = (cb.respond_to?(:filter) ? cb.filter : nil)
      filter_name =
        case filter
        when Symbol then filter.to_s
        when String then filter.to_s
        else
          if filter.respond_to?(:name)
            filter.name.to_s
          else
            filter.to_s
          end
        end

      source_file = nil
      source_line = nil
      if filter.is_a?(Symbol)
        begin
          if klass.method_defined?(filter)
            m = klass.instance_method(filter)
            if m && m.respond_to?(:source_location)
              loc = m.source_location
              source_file, source_line = loc if loc
            end
          end
        rescue StandardError
          # ignore
        end
      elsif filter.respond_to?(:source_location)
        begin
          loc = filter.source_location
          source_file, source_line = loc if loc
        rescue StandardError
          # ignore
        end
      end

      options = {}
      begin
        options = cb.options if cb.respond_to?(:options)
      rescue StandardError
        options = {}
      end

      list << {
        event: event_label.to_s,
        kind: (kind ? kind.to_s : nil),
        filter: filter_name,
        options: options,
        source_file: source_file,
        source_line: source_line
      }
    rescue StandardError
      # best-effort; skip any problematic callback objects
    end
  end

  list
end

begin
  model_name = ARGV[0]
  raise ArgumentError, 'Missing model name argument' if model_name.nil? || model_name.strip.empty?

  klass = safe_constantize(model_name)
  raise ArgumentError, "Unknown constant: #{model_name}" unless klass

  # Collect callbacks from common chains
  callbacks = []
  callbacks.concat(extract_callbacks(klass, :_validation_callbacks, :validation))
  callbacks.concat(extract_callbacks(klass, :_save_callbacks, :save))
  callbacks.concat(extract_callbacks(klass, :_create_callbacks, :create)) if klass.respond_to?(:_create_callbacks)
  callbacks.concat(extract_callbacks(klass, :_update_callbacks, :update)) if klass.respond_to?(:_update_callbacks)
  callbacks.concat(extract_callbacks(klass, :_commit_callbacks, :commit)) if klass.respond_to?(:_commit_callbacks)
  callbacks.concat(extract_callbacks(klass, :_rollback_callbacks, :rollback)) if klass.respond_to?(:_rollback_callbacks)

  # Touch targets (associations with touch: true)
  touches = []
  if klass.respond_to?(:reflect_on_all_associations)
    klass.reflect_on_all_associations.each do |r|
      opts = r.options || {}
      if opts[:touch]
        touches << {
          name: r.name.to_s,
          macro: r.macro.to_s,
          class_name: (r.respond_to?(:class_name) ? r.class_name : (r.klass&.name rescue nil)),
          options: { touch: opts[:touch] }
        }
      end
    end
  end

  # Dependents (all associations with a dependent option)
  dependents = []
  if klass.respond_to?(:reflect_on_all_associations)
    klass.reflect_on_all_associations.each do |r|
      dep = (r.options || {})[:dependent]
      next unless dep
      dependents << {
        name: r.name.to_s,
        macro: r.macro.to_s,
        class_name: (r.respond_to?(:class_name) ? r.class_name : (r.klass&.name rescue nil)),
        dependent: dep.to_s
      }
    end
  end

  output = {
    model: model_name,
    callbacks: callbacks,
    touches: touches,
    dependents: dependents
  }

  puts JSON.generate(output)
rescue StandardError => e
  warn_msg = { error: e.class.name, message: e.message, backtrace: (e.backtrace || [])[0..5] }
  puts JSON.generate(warn_msg)
end

