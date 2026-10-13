// WalletPanel.jsx
import React, { useState, useEffect } from 'react';
import { LucideDollarSign } from 'lucide-react';

const WalletPanel = () => {
  const [balance, setBalance] = useState({ total: 0, earned: 0, spent: 0 });
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    fetch('/api/sigma_network/wallet')
      .then(response => response.json())
      .then(data => {
        setBalance(data.balance);
        setTransactions(data.transactions);
      });
  }, []);

  return (
    <div className='wallet-panel'>
      <h2>Wallet</h2>
      <div className='balance'>
        <LucideDollarSign size={24} />
        <span>{balance.total} AiloCoin</span>
      </div>
      <div className='details'>
        <p>Earned: {balance.earned} AiloCoin</p>
        <p>Spent: {balance.spent} AiloCoin</p>
      </div>
      <h3>Transaction History</h3>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Counterparty</th>
            <th>Model</th>
            <th>Token</th>
            <th>Amount</th>
            <th>Signature Status</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx, index) => (
            <tr key={index}>
              <td>{tx.date}</td>
              <td>{tx.counterparty}</td>
              <td>{tx.model}</td>
              <td>{tx.token}</td>
              <td>{tx.amount}</td>
              <td>{tx.signatureStatus}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default WalletPanel;
