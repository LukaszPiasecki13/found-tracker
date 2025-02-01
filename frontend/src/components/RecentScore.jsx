import * as React from 'react';
import Link from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import Title from './Title';
import dayjs from "dayjs";

function preventDefault(event) {
  event.preventDefault();
}

export default function RecentScore({value}) {
  
  return (
    <React.Fragment>
      <Title>Recent Score</Title>
      <Typography component="p" variant="h4">
        ${value}
      </Typography>
      <Typography color="text.secondary" sx={{ flex: 1 }}>
        {dayjs().format("D MMMM, YYYY")}
      </Typography>
      <div>
        <Link color="primary" href="#" onClick={preventDefault}>
          View balance
        </Link>
      </div>
    </React.Fragment>
  );
}
