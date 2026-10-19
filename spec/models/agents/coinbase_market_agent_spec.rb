require 'rails_helper'

describe Agents::CoinbaseMarketAgent do
  let(:agent) do
    described_class.create!(
      name: 'Coinbase ticker',
      user: users(:jane),
      options: {
        'product_id' => 'BTC-USD',
        'signal_threshold_percent' => '1',
        'expected_update_period_in_days' => '1'
      }
    )
  end

  let(:ticker_url) { 'https://api.exchange.coinbase.com/products/BTC-USD/ticker' }

  def created_events
    agent.events.reorder(:id)
  end

  def stub_ticker(price:, volume: '12.5', time: '2026-10-19T12:00:00Z')
    stub_request(:get, ticker_url).to_return(
      status: 200,
      headers: { 'Content-Type' => 'application/json' },
      body: { price: price.to_s, volume: volume, time: time }.to_json
    )
  end

  it 'has safe defaults for a Coinbase BTC-USD spot market' do
    agent = described_class.new(name: 'Coinbase ticker', user: users(:jane))

    expect(agent.options).to include(
      'product_id' => 'BTC-USD',
      'signal_threshold_percent' => '1.0',
      'disable_redirect_follow' => true
    )
    expect(agent).to be_valid
  end

  it 'rejects malformed product IDs and invalid thresholds' do
    agent.options['product_id'] = 'https://example.com'
    agent.options['signal_threshold_percent'] = '0'

    expect(agent).not_to be_valid
  end

  it 'emits a hold event for the first valid public ticker sample' do
    stub_ticker(price: 100)

    expect { agent.check }.to change(agent.events, :count).by(1)
    expect(created_events.last.payload).to include(
      'exchange' => 'coinbase',
      'product_id' => 'BTC-USD',
      'price' => 100.0,
      'signal' => 'hold'
    )
    expect(agent.memory['last_price']).to eq(100.0)
  end

  it 'emits threshold signals based on the previous successful sample' do
    stub_ticker(price: 100)
    agent.check
    stub_ticker(price: 101)

    agent.check

    expect(created_events.last.payload['signal']).to eq('buy')
    expect(created_events.last.payload['change_percent']).to eq(1.0)
  end

  it 'does not create a price event for an unsuccessful API response' do
    stub_request(:get, ticker_url).to_return(status: 503)

    expect { agent.check }.not_to change(agent.events, :count)
    expect(agent.logs.first.message).to include('HTTP 503')
  end

  it 'does not accept an invalid ticker price or overwrite the last valid price' do
    agent.memory['last_price'] = 100.0
    stub_ticker(price: 'NaN')

    expect { agent.check }.not_to change(agent.events, :count)
    expect(agent.memory['last_price']).to eq(100.0)
  end
end
