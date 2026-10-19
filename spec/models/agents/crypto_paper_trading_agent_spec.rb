require 'rails_helper'

describe Agents::CryptoPaperTradingAgent do
  let(:agent) do
    described_class.create!(
      name: 'Paper trader',
      user: users(:jane),
      options: {
        'product_id' => 'BTC-USD',
        'starting_balance_usd' => '100',
        'order_size_usd' => '25',
        'max_position_usd' => '30',
        'daily_loss_limit_usd' => '5',
        'paused' => false
      }
    )
  end

  def market_event(signal:, price: 10)
    Event.new(payload: {
      'exchange' => 'coinbase',
      'product_id' => 'BTC-USD',
      'signal' => signal,
      'price' => price
    })
  end

  it 'starts with bounded defaults and validates its portfolio limits' do
    expect(agent).to be_valid

    agent.options['order_size_usd'] = '31'
    expect(agent).not_to be_valid
  end

  it 'simulates a buy without sending orders and respects the exposure limit' do
    agent.receive([market_event(signal: 'buy')])
    agent.receive([market_event(signal: 'buy')])
    agent.receive([market_event(signal: 'buy')])

    expect(agent.events.reorder(:id).pluck(:payload).map { |payload| payload['action'] }).to eq(
      %w[paper_buy paper_buy hold]
    )
    expect(agent.memory.dig('portfolio', 'cash_usd')).to eq(70.0)
    expect(agent.memory.dig('portfolio', 'position_units')).to eq(3.0)
    expect(agent.events.last.payload).to include(
      'paper_only' => true,
      'reason' => 'Order, cash, or maximum-position limit prevents a buy'
    )
  end

  it 'closes the simulated position and blocks buys after the daily loss limit' do
    agent.receive([market_event(signal: 'buy')])
    agent.receive([market_event(signal: 'sell', price: 8)])
    agent.receive([market_event(signal: 'buy')])

    expect(agent.events.reorder(:id).pluck(:payload).map { |payload| payload['action'] }).to eq(
      %w[paper_buy paper_sell hold]
    )
    expect(agent.memory.dig('portfolio', 'daily_realized_pnl_usd')).to eq(-5.0)
    expect(agent.events.reorder(:id).last.payload['reason']).to eq('Daily realized-loss limit reached')
  end

  it 'pauses new buys but permits a sell to close an open paper position' do
    agent.receive([market_event(signal: 'buy')])
    agent.options['paused'] = true
    agent.receive([market_event(signal: 'buy')])
    agent.receive([market_event(signal: 'sell')])

    expect(agent.events.reorder(:id).pluck(:payload).map { |payload| payload['action'] }).to eq(
      %w[paper_buy hold paper_sell]
    )
    expect(agent.memory.dig('portfolio', 'position_units')).to eq(0.0)
  end

  it 'ignores mismatched products and malformed market events' do
    mismatched_product = market_event(signal: 'buy').tap { |event| event.payload['product_id'] = 'ETH-USD' }
    invalid_price = market_event(signal: 'buy', price: Float::INFINITY)

    expect { agent.receive([mismatched_product, invalid_price]) }.not_to change(agent.events, :count)
  end
end
